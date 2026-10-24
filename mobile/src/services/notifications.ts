/**
 * Check-in notifications.
 *
 * These are "local" notifications: the phone itself schedules them, no server
 * is involved. They fire even if the app is closed.
 *
 * For each check-in we schedule two:
 *   1. A reminder shortly before your return time.
 *   2. An "overdue" warning at your return time.
 */

import { Platform } from 'react-native';

const CHANNEL_ID = 'check-ins';
const REMINDER_MINUTES_BEFORE = 10;

/**
 * Why we don't simply `import * as Notifications from 'expo-notifications'`:
 *
 * Loading the whole library also loads its push-notification parts, and Expo Go
 * on Android no longer includes those, which crashes the app on startup
 * ("Cannot find native module 'ExpoTopicSubscriptionModule'").
 *
 * So we load only the pieces we use for local notifications, and do it inside
 * try/catch: if anything is still missing, notifications are switched off
 * instead of crashing the whole app.
 */
function loadNotifications() {
  if (Platform.OS === 'web') return null; // not supported in the web preview
  try {
    /* eslint-disable @typescript-eslint/no-require-imports */
    return {
      ...(require('expo-notifications/build/NotificationsHandler') as typeof import('expo-notifications/build/NotificationsHandler')),
      ...(require('expo-notifications/build/NotificationPermissions') as typeof import('expo-notifications/build/NotificationPermissions')),
      ...(require('expo-notifications/build/setNotificationChannelAsync') as typeof import('expo-notifications/build/setNotificationChannelAsync')),
      ...(require('expo-notifications/build/scheduleNotificationAsync') as typeof import('expo-notifications/build/scheduleNotificationAsync')),
      ...(require('expo-notifications/build/cancelAllScheduledNotificationsAsync') as typeof import('expo-notifications/build/cancelAllScheduledNotificationsAsync')),
      ...(require('expo-notifications/build/NotificationChannelManager.types') as typeof import('expo-notifications/build/NotificationChannelManager.types')),
      ...(require('expo-notifications/build/Notifications.types') as typeof import('expo-notifications/build/Notifications.types')),
    };
    /* eslint-enable @typescript-eslint/no-require-imports */
  } catch (error) {
    console.warn('Notifications are unavailable on this device', error);
    return null;
  }
}

// null means notifications aren't available; every function below then does nothing.
const Notifications = loadNotifications();

// Whether our "Check-in reminders" channel was created. Expo Go on Android
// can't create channels, so there we fall back to Android's default channel.
let channelReady = false;
let setupDone: Promise<void> = Promise.resolve();

/**
 * One-time setup, run when the app starts:
 * - show notifications even while the app is open
 * - create the Android "channel" (Android groups notifications into channels,
 *   which users can mute separately in Settings)
 */
export function setUpNotifications(): Promise<void> {
  setupDone = setUp();
  return setupDone;
}

async function setUp() {
  if (!Notifications) return;

  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });

  try {
    await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
      name: 'Check-in reminders',
      importance: Notifications.AndroidImportance.MAX,
    });
    channelReady = true;
  } catch {
    // Expected in Expo Go on Android. Not an error: reminders still work,
    // they just use the default channel. A real app build creates the channel.
    console.log('Notification channel unavailable (normal in Expo Go); using the default channel.');
  }
}

/** True if reminders can be shown (notification permission granted). Doesn't ask. */
export async function notificationsAllowed(): Promise<boolean> {
  if (!Notifications) return false;
  const { granted } = await Notifications.getPermissionsAsync();
  return granted;
}

/**
 * Ask the user for permission to show notifications (only asks once; after
 * that the phone remembers the answer). Returns true if allowed.
 */
export async function askNotificationPermission(): Promise<boolean> {
  if (!Notifications) return false;

  const current = await Notifications.getPermissionsAsync();
  if (current.granted) return true;

  const answer = await Notifications.requestPermissionsAsync();
  return answer.granted;
}

/**
 * Replace any scheduled check-in notifications with ones for this return time.
 * Pass null (no active check-in) to just cancel them.
 */
export async function scheduleCheckInNotifications(returnBy: Date | null) {
  if (!Notifications) return;
  await setupDone; // make sure we know whether our channel exists
  // Use our channel if it exists; otherwise let Android pick its default.
  const channelId = channelReady ? CHANNEL_ID : undefined;

  // Start clean so changing the time never leaves old notifications behind.
  await Notifications.cancelAllScheduledNotificationsAsync();
  if (!returnBy) return;

  // Don't ask for permission here; that happens when you tap "Start check-in".
  // Without permission there's nothing to schedule.
  const { granted } = await Notifications.getPermissionsAsync();
  if (!granted) return;

  const now = Date.now();
  // Remind 10 minutes before, or halfway through if the check-in is shorter
  // than 20 minutes (e.g. 2.5 min into a 5-min check-in, 30 s into a 1-min one).
  const leadMs = Math.min(REMINDER_MINUTES_BEFORE * 60 * 1000, (returnBy.getTime() - now) / 2);
  const reminderAt = new Date(returnBy.getTime() - leadMs);

  // 1. Reminder (skipped if that time has already passed).
  if (reminderAt.getTime() > now) {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: '⏰ Almost time to check in',
        body: `You're due back in ${describeLead(leadMs)}. Open Androyit and tap "I'm safe" if you're OK.`,
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: reminderAt,
        channelId,
      },
    });
  }

  // 2. Overdue warning at the return time.
  if (returnBy.getTime() > now) {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: "⚠️ You haven't checked in",
        body: "Your return time has passed and your Circle is being texted. Tap to open Androyit and check in.",
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: returnBy,
        channelId,
      },
    });
  }
}

// "30 seconds", "1 minute", "10 minutes"
function describeLead(ms: number) {
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = Math.round(seconds / 60);
  return minutes === 1 ? '1 minute' : `${minutes} minutes`;
}
