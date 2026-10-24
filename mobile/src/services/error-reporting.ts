/**
 * Crash reports. Any error the app doesn't handle is sent to our server,
 * which passes it on to Bugsnag (see backend/app/errors.py). Doing it through
 * our server keeps this working in Expo Go (no native Bugsnag module needed).
 * Reports never contain your Circle, location or phone number.
 *
 * A crash closes the app before a report can always be sent, so the report is
 * saved on the phone first and sent the next time the app opens.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { reportError } from '@/services/server';

type GlobalErrorHandler = (error: unknown, isFatal?: boolean) => void;
type ErrorUtilsType = {
  getGlobalHandler: () => GlobalErrorHandler;
  setGlobalHandler: (handler: GlobalErrorHandler) => void;
};

const PENDING_KEY = 'reached:pending-crash-report';
// How long a crash may wait for its report to be saved and sent.
const FATAL_WAIT_MS = 2500;

type Report = Parameters<typeof reportError>[0];

let installed = false;

export function setUpErrorReporting() {
  if (installed || __DEV__) return; // in development you see errors on screen
  installed = true;

  sendPendingReport();

  const errorUtils = (globalThis as { ErrorUtils?: ErrorUtilsType }).ErrorUtils;
  if (!errorUtils) return;

  const previous = errorUtils.getGlobalHandler();
  errorUtils.setGlobalHandler((error, isFatal) => {
    const report = toReport(error, isFatal ?? false);
    if (!isFatal) {
      reportError(report).catch(() => {});
      previous(error, isFatal);
      return;
    }
    // Save it first, try to send it, then let the app close as normal.
    const saveAndSend = AsyncStorage.setItem(PENDING_KEY, JSON.stringify(report))
      .then(() => reportError(report))
      .then((sent) => (sent ? AsyncStorage.removeItem(PENDING_KEY) : undefined))
      .catch(() => {});
    const timeout = new Promise((resolve) => setTimeout(resolve, FATAL_WAIT_MS));
    Promise.race([saveAndSend, timeout]).finally(() => previous(error, isFatal));
  });
}

/** Report an error that was caught but shouldn't have happened. */
export function send(error: unknown, isFatal = false) {
  reportError(toReport(error, isFatal)).catch(() => {});
}

function toReport(error: unknown, isFatal: boolean): Report {
  const err = error instanceof Error ? error : new Error(String(error));
  return {
    message: `${err.name}: ${err.message}`,
    stack: err.stack,
    isFatal,
    appVersion: Constants.expoConfig?.version,
    platform: Platform.OS,
  };
}

// A crash report saved by the last run (the app closed before sending it).
async function sendPendingReport() {
  try {
    const text = await AsyncStorage.getItem(PENDING_KEY);
    if (!text) return;
    const report = JSON.parse(text) as Report;
    const sent = await reportError({ ...report, message: `[previous run] ${report.message}` });
    if (sent) await AsyncStorage.removeItem(PENDING_KEY);
  } catch {
    // Try again next launch.
  }
}
