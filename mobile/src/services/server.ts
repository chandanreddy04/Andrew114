/**
 * Talking to the server (the Reached API in backend/).
 *
 * The server is what makes the app trustworthy: it keeps watching your
 * check-in even if your phone dies, and texts your Circle if you don't check
 * in on time (a timer on the server's Celery worker).
 *
 * Every function here returns null / false instead of throwing when the
 * server can't be reached, so the rest of the app can carry on and tell
 * you what happened.
 */

import { getSession, onSessionChange, publicRequest, request, saveTokens, setSession } from '@/services/api';
import type { Contact } from '@/state/safety-store';

// ----- Logging in with your phone number -----
//
// 1. sendLoginCode(phone): the server texts a 6-digit code (via Twilio).
// 2. verifyLoginCode(phone, code): if the code is right, you're logged in.
// The login is remembered between app launches (in secure storage).

/** The logged-in phone number (e.g. "+15551234567"), or null if not logged in. */
export async function getLoggedInPhone(): Promise<string | null> {
  return (await getSession())?.phone ?? null;
}

/** Calls `onChange` whenever you log in or out. Returns a function to stop listening. */
export function onLoginChange(onChange: () => void): () => void {
  return onSessionChange(onChange);
}

/** Text a login code to this number. Returns an error message, or null if sent. */
export async function sendLoginCode(phone: string): Promise<string | null> {
  const result = await publicRequest('POST', '/v1/auth/send-code', { phone });
  return result.ok ? null : result.error;
}

/** Check the code. Returns an error message, or null if you're now logged in. */
export async function verifyLoginCode(phone: string, code: string): Promise<string | null> {
  const result = await publicRequest<Parameters<typeof saveTokens>[0]>('POST', '/v1/auth/verify', {
    phone,
    code,
  });
  if (!result.ok) return result.error;
  await saveTokens(result.data);
  return null;
}

export async function logOut(): Promise<void> {
  const session = await getSession();
  if (session) {
    // Tell the server to forget this login (fine if it can't be reached).
    await publicRequest('POST', '/v1/auth/logout', { refresh_token: session.refreshToken });
  }
  await setSession(null);
}

/**
 * Permanently delete your account and everything stored about you on the
 * server. Returns an error message, or null if deleted.
 */
export async function deleteAccount(): Promise<string | null> {
  const result = await request('DELETE', '/v1/me');
  return result.ok ? null : result.error;
}

// ----- Contacts -----

export async function fetchContacts(): Promise<Contact[] | null> {
  const result = await request<Contact[]>('GET', '/v1/contacts');
  if (!result.ok) {
    console.warn('Could not load contacts from server:', result.error);
    return null;
  }
  return result.data;
}

export async function insertContact(name: string, phone: string): Promise<Contact | null> {
  const result = await request<Contact>('POST', '/v1/contacts', { name, phone });
  if (!result.ok) {
    console.warn('Could not save contact:', result.error);
    return null;
  }
  return result.data;
}

export async function updateContact(id: string, name: string, phone: string): Promise<Contact | null> {
  const result = await request<Contact>('PUT', `/v1/contacts/${id}`, { name, phone });
  if (!result.ok) {
    console.warn('Could not update contact:', result.error);
    return null;
  }
  return result.data;
}

export async function deleteContact(id: string): Promise<boolean> {
  const result = await request('DELETE', `/v1/contacts/${id}`);
  if (!result.ok) console.warn('Could not delete contact:', result.error);
  // Already gone on the server counts as deleted.
  return result.ok || result.status === 404;
}

// ----- Check-ins -----

export type ServerCheckInStatus = 'active' | 'safe' | 'missed';

// The phone's time zone, e.g. "America/New_York", so texts to your Circle
// show your local time.
function timeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? null;
  } catch {
    return null;
  }
}

/**
 * Start a check-in on the server, or move the return time of the one that's
 * already active (you can only have one active check-in at a time). The
 * server sets a timer for the return time. Returns the server's id for it.
 */
export async function startOrUpdateCheckIn(returnBy: Date): Promise<string | null> {
  const result = await request<{ id: string }>('PUT', '/v1/check-ins/active', {
    return_by: returnBy.toISOString(),
    time_zone: timeZone(),
  });
  if (!result.ok) {
    console.warn('Could not start check-in:', result.error);
    return null;
  }
  return result.data.id;
}

// What really happened when you tapped "I'm safe".
export type EndCheckInResult =
  | { reached: false } // couldn't reach the server
  | { reached: true; alreadyMissed: false } // marked safe in time: nobody alerted
  // Too late: already missed. alertsSummary says what was actually sent,
  // e.g. "Texted 1 of 1", "Texted 0 of 2 (…errors…)" or "No one in Circle".
  // allClearSending: your Circle was alerted, so they're now being texted that you're safe.
  | {
      reached: true;
      alreadyMissed: true;
      alertsSentAt: string | null;
      alertsSummary: string | null;
      allClearSending: boolean;
    };

type ConfirmSafeResponse = {
  result: 'safe' | 'already_missed';
  alerts_sent_at: string | null;
  alerts_summary: string | null;
  all_clear_sending: boolean;
};

/**
 * Tell the server you're safe. If the check-in is still active it's simply
 * ended. If the server already marked it missed and texted your Circle, it
 * stays "missed" in your history and your Circle gets an "all clear" text
 * (sent by the server straight away).
 */
export async function markCheckInSafe(id: string): Promise<EndCheckInResult> {
  const result = await request<ConfirmSafeResponse>('POST', `/v1/check-ins/${id}/safe`);
  if (!result.ok) {
    console.warn('Could not confirm safe:', result.error);
    return { reached: false };
  }
  const data = result.data;
  if (data.result === 'safe') return { reached: true, alreadyMissed: false };
  return {
    reached: true,
    alreadyMissed: true,
    alertsSentAt: data.alerts_sent_at,
    alertsSummary: data.alerts_summary,
    allClearSending: data.all_clear_sending,
  };
}

export type ServerCheckIn = {
  status: ServerCheckInStatus;
  alertsSentAt: string | null; // when the server texted your Circle
  alertsSummary: string | null; // e.g. "Texted 2 of 2"
};

/** Ask the server what it currently knows about this check-in. */
export async function fetchCheckInStatus(id: string): Promise<ServerCheckIn | null> {
  const result = await request<{
    status: ServerCheckInStatus;
    alerts_sent_at: string | null;
    alerts_summary: string | null;
  }>('GET', `/v1/check-ins/${id}`);
  if (!result.ok) return null;
  return {
    status: result.data.status,
    alertsSentAt: result.data.alerts_sent_at,
    alertsSummary: result.data.alerts_summary,
  };
}

// ----- History -----

export type HistoryItem =
  | {
      kind: 'check-in';
      at: string; // when it started
      returnBy: string;
      status: ServerCheckInStatus;
      endedAt: string | null; // when you tapped "I'm safe" in time
      alertsSummary: string | null; // e.g. "Texted 1 of 1"
      confirmedSafeAt: string | null; // tapped "I'm safe" after it was missed
      allClearSummary: string | null; // e.g. "Texted 1 of 1", "Not needed: …"
    }
  | {
      kind: 'sos';
      at: string;
      alertsSummary: string | null;
      hadLocation: boolean;
    };

type HistoryResponse = (
  | {
      kind: 'check-in';
      at: string;
      return_by: string;
      status: ServerCheckInStatus;
      ended_at: string | null;
      alerts_summary: string | null;
      confirmed_safe_at: string | null;
      all_clear_summary: string | null;
    }
  | { kind: 'sos'; at: string; alerts_summary: string | null; had_location: boolean }
)[];

/** Your most recent check-ins and SOS alerts, newest first (null if offline). */
export async function fetchHistory(limit = 20): Promise<HistoryItem[] | null> {
  const result = await request<HistoryResponse>('GET', `/v1/history?limit=${limit}`);
  if (!result.ok) return null;
  return result.data.map((item) =>
    item.kind === 'sos'
      ? {
          kind: 'sos' as const,
          at: item.at,
          alertsSummary: item.alerts_summary,
          hadLocation: item.had_location,
        }
      : {
          kind: 'check-in' as const,
          at: item.at,
          returnBy: item.return_by,
          status: item.status,
          endedAt: item.ended_at,
          alertsSummary: item.alerts_summary,
          confirmedSafeAt: item.confirmed_safe_at,
          allClearSummary: item.all_clear_summary,
        },
  );
}

// ----- Your name -----

export async function fetchProfileName(): Promise<string | null> {
  const result = await request<{ display_name: string | null }>('GET', '/v1/me');
  return result.ok ? result.data.display_name : null;
}

export async function saveProfileName(name: string): Promise<boolean> {
  const result = await request('PUT', '/v1/me', { display_name: name });
  if (!result.ok) console.warn('Could not save name:', result.error);
  return result.ok;
}

// ----- SOS -----

export type SosResult =
  // trialTemplate: Twilio is on a trial account, so a generic Twilio sample
  // text was sent instead of the real SOS message.
  | { ok: true; sent: number; total: number; errors: string[]; trialTemplate: boolean }
  | { ok: false; error: string };

/** Ask the server to text your whole Circle with your location. */
export async function sendSos(
  location: { latitude: number; longitude: number; accuracyMeters: number | null } | null,
): Promise<SosResult> {
  const result = await request<{
    sent: number;
    total: number;
    errors: string[];
    trial_template: boolean;
  }>(
    'POST',
    '/v1/sos',
    location
      ? {
          latitude: location.latitude,
          longitude: location.longitude,
          accuracy_meters: location.accuracyMeters,
        }
      : {},
  );
  // The server's own message, e.g. "Too many SOS alerts…".
  if (!result.ok) return { ok: false, error: result.error };
  return {
    ok: true,
    sent: result.data.sent,
    total: result.data.total,
    errors: result.data.errors ?? [],
    trialTemplate: result.data.trial_template === true,
  };
}

// ----- Crash reports (forwarded to Bugsnag by the server) -----

export async function reportError(details: {
  message: string;
  stack?: string;
  isFatal: boolean;
  appVersion?: string;
  platform?: string;
}): Promise<void> {
  if (!(await getSession())) return; // reports are tied to a login (prevents spam)
  await request('POST', '/v1/client-errors', {
    message: details.message.slice(0, 2000),
    stack: details.stack?.slice(0, 20000),
    is_fatal: details.isFatal,
    app_version: details.appVersion,
    platform: details.platform,
  });
}
