/**
 * Your phone's battery level, shared with your Circle when you press SOS (so
 * they know how long your phone may stay reachable).
 */

import { Platform } from 'react-native';

import type * as BatteryTypes from 'expo-battery';

/** 0-100, or null if the phone can't tell (e.g. an older app build, the web preview). */
export async function getBatteryPercent(): Promise<number | null> {
  if (Platform.OS === 'web') return null;
  try {
    // Loaded here (inside try/catch): builds made before the battery module
    // was added simply share no battery level instead of crashing.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Battery = require('expo-battery') as typeof BatteryTypes;
    const level = await Battery.getBatteryLevelAsync();
    return level >= 0 ? Math.round(level * 100) : null;
  } catch {
    return null;
  }
}
