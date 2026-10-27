/**
 * The app's shared memory.
 *
 * Several screens need the same information (whether you're logged in, the
 * current check-in and the list of trusted contacts). Instead of each screen
 * keeping its own copy, we keep it here in one place and let any screen read
 * or change it.
 *
 * This uses React "Context": the <SafetyProvider> wraps the whole app (see
 * src/app/_layout.tsx), and any screen can call useSafety() to get the data.
 *
 * Where data lives:
 * - On the server (the Reached API, backend/): the real copy, tied to your
 *   phone-number login.
 *   The server keeps watching your check-in even if your phone dies.
 * - On the phone (AsyncStorage): a copy, so the app opens instantly and the
 *   countdown keeps working with no signal.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { AppState } from 'react-native';

import { getBatteryPercent } from '@/services/battery';
import { send as reportProblem } from '@/services/error-reporting';
import { getSosLocation } from '@/services/location';
import {
  forgetProfilePhoto,
  loadSavedPhoto,
  removeProfilePhoto,
  syncProfilePhoto,
  uploadProfilePhoto,
} from '@/services/profile-photo';
import { scheduleCheckInNotifications, setUpNotifications } from '@/services/notifications';
import {
  deleteAccount as deleteAccountOnServer,
  deleteCheckInPhoto,
  deleteContact,
  endSosOnServer,
  fetchCheckInStatus,
  fetchContacts,
  fetchProfile,
  getLoggedInPhone,
  insertContact,
  logOut as logOutOnServer,
  markCheckInSafe,
  onLoginChange,
  saveProfileName,
  sendLoginCode,
  sendSos as sendSosOnServer,
  startOrUpdateCheckIn,
  updateCheckInLocation,
  updateContact as updateContactOnServer,
  uploadCheckInPhoto,
  verifyLoginCode,
  type EndCheckInResult,
  type EndSosResult,
  type MapPosition,
  type ServerCheckIn,
  type SosResult,
} from '@/services/server';

// One person in your Circle of Trust.
export type Contact = {
  id: string;
  name: string;
  phone: string;
};

// An active check-in: when it started and when you expect to be back.
export type CheckIn = {
  startedAt: Date;
  returnBy: Date;
  // The server's copy of this check-in, or null if the server never got it.
  // alertsSentAt / alertsSummary say whether your Circle was texted.
  server: ({ id: string } & Partial<ServerCheckIn> & Pick<ServerCheckIn, 'status'>) | null;
  // Shared with your Circle only if an alert triggers:
  destination: string | null; // "Central Park"
  destinationPlace: MapPosition | null; // where it is, if picked from the address search
  shareLocation: boolean; // the "Location" switch
  locationShared: boolean; // the server has your last known location
  photoUri: string | null; // the outfit photo on this phone
  photoShared: boolean; // the server has the photo
  photoProblem: string | null; // why the photo couldn't be sent (tap Retry)
};

// An SOS you sent: active (shown on Home) until you tap "I'm safe".
export type ActiveSos = {
  startedAt: Date;
  // 'sending': getting your location and texting your Circle.
  status: 'sending' | 'sent' | 'failed';
  result: SosResult | null;
  hadLocation: boolean;
  batteryPercent: number | null;
  photoShared: boolean; // your session's outfit photo is on the details page
};

// What the Start Session screen sends. Left out = unchanged.
// photo: a new picture's file, or null to remove it.
export type SessionChoices = {
  destination?: string;
  destinationPlace?: MapPosition | null;
  shareLocation?: boolean;
  photo?: string | null;
};

// Everything a screen can read or do via useSafety().
// Functions that talk to the server return true (or null for "no error") if it worked.
type SafetyStore = {
  // ----- Welcome screens (shown once per phone, before the first login) -----
  welcomeSeen: boolean;
  markWelcomeSeen: () => void;

  // ----- Login -----
  // Your phone number while logged in; null when logged out.
  loggedInPhone: string | null;
  // Each returns an error message, or null if it worked.
  sendLoginCode: (phone: string) => Promise<string | null>;
  verifyLoginCode: (phone: string, code: string) => Promise<string | null>;
  logOut: () => Promise<string | null>;
  deleteAccount: () => Promise<string | null>;

  serverConnected: boolean;

  // Your name, used in texts to your Circle ("Alex hasn't checked in").
  profileName: string;
  setProfileName: (name: string) => Promise<boolean>;
  // Your profile picture (a file on this phone), shown to your Circle in alerts.
  profilePhotoUri: string | null;
  // A newly picked picture, or null to remove it. Returns an error message, or null.
  setProfilePhoto: (uri: string | null) => Promise<string | null>;

  checkIn: CheckIn | null;
  startCheckIn: (returnBy: Date, choices?: SessionChoices) => Promise<boolean>;
  // Try sending the outfit photo again after it failed.
  retryPhoto: () => void;
  // Says whether the server got it in time, or your Circle was already alerted.
  endCheckIn: () => Promise<EndCheckInResult>;

  contacts: Contact[];
  addContact: (name: string, phone: string) => Promise<boolean>;
  updateContact: (id: string, name: string, phone: string) => Promise<boolean>;
  removeContact: (id: string) => Promise<boolean>;

  // ----- SOS (hold the yellow button for 3 seconds) -----
  activeSos: ActiveSos | null;
  // Gets your location and battery, then texts your Circle.
  triggerSos: () => Promise<void>;
  // "I'm safe": ends the SOS and texts your Circle an all-clear.
  endSos: () => Promise<EndSosResult>;
  // 3, 2, 1 while the SOS button is held (drawn over every screen); else null.
  sosCountdown: number | null;
  setSosCountdown: (value: number | null) => void;
};

const SafetyContext = createContext<SafetyStore | null>(null);

// The names the data is saved under on the phone.
const CONTACTS_KEY = 'reached:contacts';
const CHECK_IN_KEY = 'reached:check-in';
const NAME_KEY = 'reached:name';
const SOS_KEY = 'reached:sos';
// Kept on log-out: the welcome is about the phone, not the account.
const WELCOME_KEY = 'reached:welcome-seen';

// How often to ask the server about the active check-in.
const STATUS_POLL_MS = 30 * 1000;
// Refresh your last known location at most this often (when the app opens).
const LOCATION_REFRESH_MS = 5 * 60 * 1000;

// ----- Loading from the phone -----
// AsyncStorage only stores text, so we turn data into JSON text when saving
// and back into objects (and Dates) when loading.

async function loadContacts(): Promise<Contact[]> {
  const text = await AsyncStorage.getItem(CONTACTS_KEY);
  if (!text) return [];
  const parsed = JSON.parse(text);
  return Array.isArray(parsed) ? parsed : [];
}

async function loadCheckIn(): Promise<CheckIn | null> {
  const text = await AsyncStorage.getItem(CHECK_IN_KEY);
  if (!text) return null;
  const parsed = JSON.parse(text);
  // Dates were saved as text like "2026-10-16T21:30:00.000Z"; turn them back into Dates.
  const checkIn: CheckIn = {
    startedAt: new Date(parsed.startedAt),
    returnBy: new Date(parsed.returnBy),
    server: parsed.server ?? null,
    destination: parsed.destination ?? null,
    destinationPlace: parsed.destinationPlace ?? null,
    shareLocation: parsed.shareLocation ?? true,
    locationShared: parsed.locationShared ?? false,
    photoUri: parsed.photoUri ?? null,
    photoShared: parsed.photoShared ?? false,
    photoProblem: parsed.photoProblem ?? null,
  };
  return isNaN(checkIn.returnBy.getTime()) ? null : checkIn;
}

async function loadSos(): Promise<ActiveSos | null> {
  const text = await AsyncStorage.getItem(SOS_KEY);
  if (!text) return null;
  const parsed = JSON.parse(text);
  const sos: ActiveSos = { ...parsed, startedAt: new Date(parsed.startedAt) };
  // A send that was cut off (app closed mid-way) can't be resumed.
  if (sos.status === 'sending') sos.status = 'failed';
  return isNaN(sos.startedAt.getTime()) ? null : sos;
}

export function SafetyProvider({ children }: { children: ReactNode }) {
  // useState holds a value and re-draws the screen whenever it changes.
  const [checkIn, setCheckIn] = useState<CheckIn | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  // False until the saved data and login state have been read.
  const [loaded, setLoaded] = useState(false);
  const [loggedInPhone, setLoggedInPhone] = useState<string | null>(null);
  const [serverConnected, setServerConnected] = useState(false);
  const [profileName, setProfileNameState] = useState('');
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [activeSos, setActiveSos] = useState<ActiveSos | null>(null);
  const [profilePhotoUri, setProfilePhotoUri] = useState<string | null>(null);
  const [sosCountdown, setSosCountdown] = useState<number | null>(null);

  // 1) When the app opens: read the phone's copy (fast) and whether you're logged in.
  useEffect(() => {
    async function load() {
      setUpNotifications().catch((error) => console.warn('Could not set up notifications', error));
      try {
        const [localContacts, localCheckIn, localName, seen, localSos, localPhoto] =
          await Promise.all([
            loadContacts(),
            loadCheckIn(),
            AsyncStorage.getItem(NAME_KEY),
            AsyncStorage.getItem(WELCOME_KEY),
            loadSos().catch(() => null),
            loadSavedPhoto(),
          ]);
        setContacts(localContacts);
        setActiveSos(localSos);
        setProfilePhotoUri(localPhoto?.uri ?? null);
        setCheckIn(localCheckIn);
        setProfileNameState(localName ?? '');
        setWelcomeSeen(seen === 'yes');
      } catch (error) {
        // Saved data was unreadable: start fresh rather than crash.
        console.warn('Could not load saved data', error);
      }
      setLoggedInPhone(await getLoggedInPhone().catch(() => null));
      setLoaded(true);
    }
    load();

    // Keep track of logging in and out (e.g. after entering the login code).
    return onLoginChange(async () => {
      setLoggedInPhone(await getLoggedInPhone().catch(() => null));
    });
  }, []);

  // 2) Once logged in, sync with the server.
  useEffect(() => {
    if (!loaded || !loggedInPhone) return;

    async function syncWithServer() {
      // Read the phone's copy again so we sync the latest data.
      const [localContacts, localCheckIn, localName] = await Promise.all([
        loadContacts().catch(() => [] as Contact[]),
        loadCheckIn().catch(() => null),
        AsyncStorage.getItem(NAME_KEY).catch(() => null),
      ]);

      // Contacts: the server's list is the real one. For a brand-new account,
      // upload the contacts saved on this phone (e.g. from before logging in).
      let serverContacts = await fetchContacts();
      if (serverContacts === null) return;
      if (serverContacts.length === 0 && localContacts.length > 0) {
        for (const c of localContacts) await insertContact(c.name, c.phone);
        serverContacts = (await fetchContacts()) ?? serverContacts;
      }
      setContacts(serverContacts);

      // Your name: use the server's copy, or upload the phone's copy if the
      // server has none yet.
      const profile = await fetchProfile();
      const serverName = profile?.displayName ?? null;
      if (profile) {
        // Profile picture: match the server's (e.g. after logging in on a new phone).
        syncProfilePhoto(profile.photoUpdatedAt).then((photo) =>
          setProfilePhotoUri(photo?.uri ?? null),
        );
      }
      if (serverName) {
        setProfileNameState(serverName);
        AsyncStorage.setItem(NAME_KEY, serverName).catch(() => {});
      } else if (localName) {
        await saveProfileName(localName);
      }

      // Check-in: make sure the server has the current one. It may be missing
      // if it was started offline, or the server no longer knows it.
      if (localCheckIn && localCheckIn.returnBy.getTime() > Date.now()) {
        const onServer = localCheckIn.server && (await fetchCheckInStatus(localCheckIn.server.id));
        if (!onServer) {
          const id = await startOrUpdateCheckIn(localCheckIn.returnBy, {
            destination: localCheckIn.destination ?? undefined,
            destinationPlace: localCheckIn.destinationPlace,
            shareLocation: localCheckIn.shareLocation,
          });
          setCheckIn({ ...localCheckIn, server: id ? { id, status: 'active' } : null });
        }
      }

      setServerConnected(true);
    }

    syncWithServer().catch((error) => console.warn('Sync failed', error));
  }, [loaded, loggedInPhone]);

  // Keep the phone's copy of an active SOS (so it's still shown after a restart).
  useEffect(() => {
    if (!loaded) return;
    const saving = activeSos
      ? AsyncStorage.setItem(SOS_KEY, JSON.stringify(activeSos))
      : AsyncStorage.removeItem(SOS_KEY);
    saving.catch(() => {});
  }, [activeSos, loaded]);

  // 3) Whenever contacts change (after loading), save the phone's copy.
  useEffect(() => {
    if (!loaded) return; // don't overwrite saved data with the empty starting list
    AsyncStorage.setItem(CONTACTS_KEY, JSON.stringify(contacts)).catch((error) =>
      console.warn('Could not save contacts', error),
    );
  }, [contacts, loaded]);

  // 4) Whenever the check-in changes (after loading), save the phone's copy, or
  //    delete it when it ends. Also reschedule (or cancel) the reminders.
  const returnByTime = checkIn?.returnBy.getTime() ?? null;
  useEffect(() => {
    if (!loaded) return;
    const saving = checkIn
      ? AsyncStorage.setItem(CHECK_IN_KEY, JSON.stringify(checkIn))
      : AsyncStorage.removeItem(CHECK_IN_KEY);
    saving.catch((error) => console.warn('Could not save check-in', error));
  }, [checkIn, loaded]);

  useEffect(() => {
    if (!loaded) return;
    // Only depends on the return time, so a server status update doesn't
    // needlessly cancel and re-create the notifications.
    scheduleCheckInNotifications(returnByTime === null ? null : new Date(returnByTime)).catch(
      (error) => console.warn('Could not schedule notifications', error),
    );
  }, [returnByTime, loaded]);

  // 5) While a check-in is on the server, ask it every 30 seconds (and whenever
  //    the app comes back to the front) whether it has marked it missed.
  const serverId = checkIn?.server?.id ?? null;
  useEffect(() => {
    if (!serverId || !loggedInPhone) return;

    async function refresh() {
      const latest = await fetchCheckInStatus(serverId!);
      if (!latest) return; // couldn't reach the server; try again next time
      setCheckIn((current) =>
        current?.server?.id === serverId
          ? { ...current, server: { id: serverId!, ...latest } }
          : current,
      );
    }

    refresh();
    const timer = setInterval(refresh, STATUS_POLL_MS);
    const appState = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => {
      clearInterval(timer);
      appState.remove();
    };
  }, [serverId, loggedInPhone]);

  // Send your last known location for this session, if the Location switch
  // is on. Never blocks anything: a missing GPS fix just means no location.
  const lastLocationAt = useRef(0);
  async function shareLocationNow(id: string) {
    lastLocationAt.current = Date.now();
    const location = await getSosLocation().catch(() => null);
    if (!location || !(await updateCheckInLocation(id, location))) return;
    setCheckIn((current) =>
      current?.server?.id === id ? { ...current, locationShared: true } : current,
    );
  }

  // Send the outfit photo. A failure is shown on Home (with Retry) and
  // reported, never silently left as "uploading".
  async function sendPhoto(id: string, uri: string) {
    setCheckIn((current) =>
      current?.server?.id === id ? { ...current, photoProblem: null } : current,
    );
    let problem: string | null;
    try {
      problem = await uploadCheckInPhoto(id, uri);
    } catch (error) {
      problem = error instanceof Error ? error.message : String(error);
    }
    if (problem) reportProblem(new Error(`Photo upload failed: ${problem} [${uri.split(':')[0]}]`));
    setCheckIn((current) =>
      current?.server?.id === id
        ? { ...current, photoShared: !problem, photoProblem: problem }
        : current,
    );
  }

  // While a session is going, refresh the location when you open the app.
  const shareLocationOn = checkIn?.shareLocation ?? false;
  const activeId = checkIn?.server?.status === 'active' ? checkIn.server.id : null;
  useEffect(() => {
    if (!activeId || !shareLocationOn) return;
    const appState = AppState.addEventListener('change', (state) => {
      if (state === 'active' && Date.now() - lastLocationAt.current > LOCATION_REFRESH_MS) {
        shareLocationNow(activeId);
      }
    });
    return () => appState.remove();
  }, [activeId, shareLocationOn]);

  // Remove everything about this account from the phone (after log out / delete).
  async function clearPhoneData() {
    setCheckIn(null);
    setContacts([]);
    setProfileNameState('');
    setServerConnected(false);
    setActiveSos(null);
    setProfilePhotoUri(null);
    await forgetProfilePhoto();
    await AsyncStorage.multiRemove([CONTACTS_KEY, CHECK_IN_KEY, NAME_KEY, SOS_KEY]).catch(() => {});
  }

  const store: SafetyStore = {
    welcomeSeen,
    markWelcomeSeen: () => {
      setWelcomeSeen(true);
      AsyncStorage.setItem(WELCOME_KEY, 'yes').catch(() => {});
    },

    loggedInPhone,
    sendLoginCode,
    verifyLoginCode,
    logOut: async () => {
      // Logging out mid check-in would leave a check-in you can't end, and
      // your Circle would get a false alarm.
      if (checkIn) return 'End your check-in (tap "I\'m safe") before logging out.';
      await logOutOnServer();
      await clearPhoneData();
      return null;
    },
    deleteAccount: async () => {
      const error = await deleteAccountOnServer();
      if (error) return error;
      await logOutOnServer();
      await clearPhoneData();
      return null;
    },

    serverConnected,

    profileName,
    setProfileName: async (name) => {
      const trimmed = name.trim();
      if (!(await saveProfileName(trimmed))) return false;
      setProfileNameState(trimmed);
      AsyncStorage.setItem(NAME_KEY, trimmed).catch(() => {});
      return true;
    },

    profilePhotoUri,
    setProfilePhoto: async (uri) => {
      if (uri === null) {
        if (!(await removeProfilePhoto())) return "The server couldn't be reached. Check your internet.";
        setProfilePhotoUri(null);
        return null;
      }
      const result = await uploadProfilePhoto(uri);
      if (!result.ok) return result.error;
      setProfilePhotoUri(result.photo.uri);
      return null;
    },

    checkIn,
    startCheckIn: async (returnBy, choices = {}) => {
      const previous = checkIn;
      const id = await startOrUpdateCheckIn(returnBy, {
        destination: choices.destination,
        destinationPlace: choices.destinationPlace,
        shareLocation: choices.shareLocation,
      });
      const sameSession = id !== null && previous?.server?.id === id;
      const photoUri = choices.photo !== undefined ? choices.photo : (previous?.photoUri ?? null);
      const shareLocation = choices.shareLocation ?? previous?.shareLocation ?? true;
      setCheckIn({
        startedAt: previous?.startedAt ?? new Date(),
        returnBy,
        server: id ? { ...(sameSession ? previous?.server : {}), id, status: 'active' } : null,
        destination: choices.destination ?? previous?.destination ?? null,
        destinationPlace:
          choices.destination !== undefined
            ? (choices.destinationPlace ?? null)
            : (previous?.destinationPlace ?? null),
        shareLocation,
        locationShared: sameSession && shareLocation ? (previous?.locationShared ?? false) : false,
        photoUri,
        photoShared: sameSession && choices.photo === undefined ? (previous?.photoShared ?? false) : false,
        photoProblem: sameSession && choices.photo === undefined ? (previous?.photoProblem ?? null) : null,
      });

      if (id) {
        // Photo and location go up in the background, so starting is instant.
        if (choices.photo) {
          sendPhoto(id, choices.photo);
        } else if (choices.photo === null && previous?.photoShared && sameSession) {
          deleteCheckInPhoto(id).catch(() => {});
        }
        if (shareLocation && (!sameSession || choices.shareLocation !== undefined)) {
          shareLocationNow(id);
        }
      }
      return id !== null;
    },
    retryPhoto: () => {
      const id = checkIn?.server?.id;
      if (id && checkIn?.photoUri) sendPhoto(id, checkIn.photoUri);
    },
    endCheckIn: async () => {
      const id = checkIn?.server?.id;
      const result: EndCheckInResult = id ? await markCheckInSafe(id) : { reached: false };
      setCheckIn(null); // always end it on the phone
      return result;
    },

    contacts,
    addContact: async (name, phone) => {
      const saved = await insertContact(name.trim(), phone.trim());
      if (!saved) return false;
      setContacts((current) => [...current, saved]);
      return true;
    },
    updateContact: async (id, name, phone) => {
      const saved = await updateContactOnServer(id, name.trim(), phone.trim());
      if (!saved) return false;
      setContacts((current) => current.map((c) => (c.id === id ? saved : c)));
      return true;
    },
    removeContact: async (id) => {
      if (!(await deleteContact(id))) return false;
      setContacts((current) => current.filter((c) => c.id !== id));
      return true;
    },

    activeSos,
    triggerSos: async () => {
      if (activeSos && activeSos.status !== 'failed') return; // one SOS at a time
      setActiveSos({
        startedAt: new Date(),
        status: 'sending',
        result: null,
        hadLocation: false,
        batteryPercent: null,
        photoShared: checkIn?.photoShared ?? false,
      });
      // Never let a location problem block the SOS: on any error, send without it.
      const [location, batteryPercent] = await Promise.all([
        getSosLocation().catch(() => null),
        getBatteryPercent(),
      ]);
      const result = await sendSosOnServer(location, batteryPercent);
      setActiveSos((current) =>
        current
          ? {
              ...current,
              status: result.ok ? 'sent' : 'failed',
              result,
              hadLocation: location !== null,
              batteryPercent,
            }
          : current,
      );
    },
    endSos: async () => {
      const id = activeSos?.result?.ok ? activeSos.result.id : null;
      const result: EndSosResult = id
        ? await endSosOnServer(id)
        : { reached: true, allClearSent: false }; // never reached the server
      if (result.reached) setActiveSos(null);
      return result;
    },
    sosCountdown,
    setSosCountdown,
  };

  // Show nothing until the saved data is loaded. The splash screen stays up
  // meanwhile, so you never briefly see an empty Circle.
  if (!loaded) return null;

  return <SafetyContext.Provider value={store}>{children}</SafetyContext.Provider>;
}

// Screens call this to get the shared data, e.g. const { contacts } = useSafety();
export function useSafety() {
  const store = useContext(SafetyContext);
  if (!store) {
    throw new Error('useSafety must be used inside <SafetyProvider>');
  }
  return store;
}
