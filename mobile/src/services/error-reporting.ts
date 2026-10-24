/**
 * Crash reports. Any error the app doesn't handle is sent to our server,
 * which passes it on to Bugsnag (see backend/app/errors.py). Doing it through
 * our server keeps this working in Expo Go (no native Bugsnag module needed).
 * Reports never contain your Circle, location or phone number.
 */

import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { reportError } from '@/services/server';

type GlobalErrorHandler = (error: unknown, isFatal?: boolean) => void;
type ErrorUtilsType = {
  getGlobalHandler: () => GlobalErrorHandler;
  setGlobalHandler: (handler: GlobalErrorHandler) => void;
};

let installed = false;

export function setUpErrorReporting() {
  if (installed || __DEV__) return; // in development you see errors on screen
  installed = true;

  const errorUtils = (globalThis as { ErrorUtils?: ErrorUtilsType }).ErrorUtils;
  if (!errorUtils) return;

  const previous = errorUtils.getGlobalHandler();
  errorUtils.setGlobalHandler((error, isFatal) => {
    send(error, isFatal ?? false);
    previous(error, isFatal); // keep the normal behaviour (e.g. the crash screen)
  });
}

/** Report an error that was caught but shouldn't have happened. */
export function send(error: unknown, isFatal = false) {
  const err = error instanceof Error ? error : new Error(String(error));
  reportError({
    message: `${err.name}: ${err.message}`,
    stack: err.stack,
    isFatal,
    appVersion: Constants.expoConfig?.version,
    platform: Platform.OS,
  }).catch(() => {});
}
