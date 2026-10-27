/**
 * Getting your location for SOS, and a rough one for the address search.
 *
 * We only ask for location "while the app is in use" and only when you press
 * SOS. No background tracking, in keeping with the app's privacy promise.
 */

import type * as LocationTypes from 'expo-location';

const GPS_TIMEOUT_MS = 10 * 1000;

export type SosLocation = {
  latitude: number;
  longitude: number;
  accuracyMeters: number | null; // how precise the fix is (smaller is better)
  isApproximate: boolean; // true if we fell back to the last known position
  mapsUrl: string; // the link your Circle would receive
};

/**
 * Ask for permission (first time only) and get your current location.
 * Returns null if permission was refused or no location could be found.
 */
export async function getSosLocation(): Promise<SosLocation | null> {
  // Load the location library only when SOS is pressed. If it's ever missing
  // on a device, this fails here (and SOS continues without a location)
  // instead of crashing the app on startup.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Location = require('expo-location') as typeof LocationTypes;

  const { granted } = await Location.requestForegroundPermissionsAsync();
  if (!granted) return null;

  // Try for a fresh, precise GPS fix. Indoors this can be slow, so give up
  // after 10 seconds and use the phone's last known position instead.
  let position: LocationTypes.LocationObject | null = null;
  let isApproximate = false;
  try {
    position = await withTimeout(
      Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High }),
      GPS_TIMEOUT_MS,
    );
  } catch {
    isApproximate = true;
    position = await Location.getLastKnownPositionAsync().catch(() => null);
  }
  if (!position) return null;

  const { latitude, longitude, accuracy } = position.coords;
  return {
    latitude,
    longitude,
    accuracyMeters: accuracy,
    isApproximate,
    mapsUrl: `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`,
  };
}

// Waits for `promise`, but fails if it takes longer than `ms` milliseconds.
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error('Timed out')), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

/**
 * Roughly where you are, to show nearby places first in the address search.
 * Never asks for permission: null unless location is already allowed.
 */
export async function getRoughLocation(): Promise<{ latitude: number; longitude: number } | null> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Location = require('expo-location') as typeof LocationTypes;
    const { granted } = await Location.getForegroundPermissionsAsync();
    if (!granted) return null;
    const position =
      (await Location.getLastKnownPositionAsync()) ??
      (await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Low }));
    if (!position) return null;
    return { latitude: position.coords.latitude, longitude: position.coords.longitude };
  } catch {
    return null;
  }
}

/** Whether Androyit may use your location (without asking). */
export async function isLocationAllowed(): Promise<boolean> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Location = require('expo-location') as typeof LocationTypes;
    return (await Location.getForegroundPermissionsAsync()).granted;
  } catch {
    return false;
  }
}

/**
 * The street address at a position, e.g. "1100 Congress Ave, Austin, TX",
 * worked out by the phone itself. Null if it can't tell (or on the web).
 */
export async function addressAt(latitude: number, longitude: number): Promise<string | null> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Location = require('expo-location') as typeof LocationTypes;
    const [found] = await Location.reverseGeocodeAsync({ latitude, longitude });
    if (!found) return null;
    const street = found.streetNumber && found.street ? `${found.streetNumber} ${found.street}` : (found.street ?? found.name);
    const parts = [street, found.city ?? found.subregion, found.region].filter(Boolean);
    return parts.length > 0 ? parts.join(', ') : (found.formattedAddress ?? null);
  } catch {
    return null;
  }
}
