import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { type ComponentProps, useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { BigButton } from '@/components/big-button';
import { Card } from '@/components/card';
import { Screen } from '@/components/screen';
import { SosCard } from '@/components/sos-card';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { notificationsAllowed } from '@/services/notifications';
import { useSafety } from '@/state/safety-store';
import { formatClock, formatTimer } from '@/utils/time';

// How much the -30m / +30m pills change the return time.
const ADJUST_MINUTES = 30;
// The shortest time left that -30m may leave you with.
const MIN_LEFT_MINUTES = 5;

// Short, practical tips shown in the "Safety Tip" card (one per app launch).
const SAFETY_TIPS = [
  'Lock your car doors as soon as you get in.',
  'Share your plans with someone you trust before heading out.',
  'Keep your phone charged before a night out.',
  'On a first date, meet somewhere public and busy.',
  'Trust your instincts. If something feels off, leave.',
  'Know your route home before it gets dark.',
  'Keep some cash for a taxi in case your phone dies.',
  'Check in with your Circle when plans change.',
];

// The new return time after adding `minutes`, counted from now if you're
// already overdue (so "+30m" really gives you 30 more minutes).
function extendedReturnTime(returnBy: Date, minutes: number) {
  const from = Math.max(returnBy.getTime(), Date.now());
  return new Date(from + minutes * 60 * 1000);
}

/**
 * Home screen.
 * - No active session: greeting, your Circle, and "Start a session".
 * - Active session: big countdown, ETA, -30m / +30m, monitoring status, "I'm Safe".
 * Both show a Safety Tip at the bottom.
 */
export default function HomeScreen() {
  const { checkIn, startCheckIn, endCheckIn, retryPhoto, contacts, serverConnected, profileName } =
    useSafety();
  const theme = useTheme();

  // A random tip, picked once when the screen opens.
  const [tip] = useState(() => SAFETY_TIPS[Math.floor(Math.random() * SAFETY_TIPS.length)]);

  // `now` is updated every second so the countdown keeps moving.
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (!checkIn) return; // no timer needed when there is no session
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer); // stop the timer when leaving the screen
  }, [checkIn]);

  // Whether reminders (notifications) are allowed, for the monitoring row.
  const [remindersOn, setRemindersOn] = useState<boolean | null>(null);
  useEffect(() => {
    notificationsAllowed()
      .then(setRemindersOn)
      .catch(() => setRemindersOn(false));
  }, [checkIn]);

  // Move the return time by `minutes` (negative = earlier).
  const [adjusting, setAdjusting] = useState(false);
  async function adjustBy(minutes: number) {
    if (!checkIn) return;
    const newTime =
      minutes > 0
        ? extendedReturnTime(checkIn.returnBy, minutes)
        : new Date(checkIn.returnBy.getTime() + minutes * 60 * 1000);
    setAdjusting(true);
    const savedToServer = await startCheckIn(newTime);
    setAdjusting(false);
    if (!savedToServer) {
      Alert.alert(
        'Changed on this phone only',
        "The server couldn't be reached, so it may still use your old time. Check your internet and try again.",
      );
    }
  }

  async function handleImSafe() {
    // Remember whether the return time had already passed before ending it.
    const wasOverdue = checkIn !== null && checkIn.returnBy.getTime() <= Date.now();
    const result = await endCheckIn();

    // Tell the truth about whether your Circle was alerted.
    if (result.reached && !result.alreadyMissed) {
      Alert.alert('Glad you made it home!', 'Your session has ended. Nobody was alerted.');
    } else if (result.reached && result.allClearSending && result.alertsSentAt) {
      Alert.alert(
        "Glad you're safe",
        `Your check-in was already missed, and your Circle was alerted at ${formatClock(new Date(result.alertsSentAt))}. We're texting them now that you're safe.`,
      );
    } else if (result.reached && result.alertsSentAt && result.alertsSummary !== 'Sending…') {
      Alert.alert("Glad you're safe", describeAlertsSent(result.alertsSentAt, result.alertsSummary));
    } else if (result.reached && result.alertsSummary === 'Sending…') {
      Alert.alert(
        "Glad you're safe",
        "Your Circle is being alerted right now about your missed check-in. As soon as that's done, we'll text them that you're safe.",
      );
    } else if (result.reached) {
      Alert.alert(
        "Glad you're safe",
        "Your check-in was already marked missed, so your Circle may have been alerted. Please let them know you're OK.",
      );
    } else {
      Alert.alert(
        'Ended on this phone only',
        wasOverdue
          ? "The server couldn't be reached. Your return time had passed, so your Circle may have been alerted. Please let them know you're OK."
          : "The server couldn't be reached, so it may still mark this check-in as missed. Check your internet.",
      );
    }
  }

  const greeting = profileName ? `Hi, ${profileName}!` : 'Hi there!';

  const header = (
    <View style={styles.header}>
      <ThemedText type="subtitle" style={styles.greeting}>
        {greeting}
      </ThemedText>
      <Pressable
        onPress={() => Alert.alert('Refer a friend', 'Coming soon.')}
        accessibilityRole="button"
        accessibilityLabel="Refer a friend (coming soon)"
        hitSlop={Spacing.three}>
        <Ionicons name="gift-outline" size={28} color={Brand.green} />
      </Pressable>
    </View>
  );

  const tipCard = (
    <View style={[styles.tipCard, { backgroundColor: theme.backgroundElement }]}>
      <View style={styles.tipTitleRow}>
        <Ionicons name="bulb" size={22} color="#F5C518" />
        <ThemedText type="smallBold" style={styles.tipTitle}>
          Safety Tip
        </ThemedText>
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        {tip}
      </ThemedText>
    </View>
  );

  // ----- Active session -----
  if (checkIn) {
    const msLeft = checkIn.returnBy.getTime() - now.getTime();
    const overdue = msLeft <= 0;
    const missed = checkIn.server?.status === 'missed';
    const canShorten = msLeft - ADJUST_MINUTES * 60 * 1000 >= MIN_LEFT_MINUTES * 60 * 1000;

    return (
      <Screen title="">
        {header}
        <SosCard />

        {/* Shown once the server has noticed you didn't check in. */}
        {missed && (
          <View style={styles.missedBanner}>
            <Text style={styles.missedTitle}>MISSED CHECK-IN</Text>
            <Text style={styles.missedBody}>
              {checkIn.server?.alertsSentAt && checkIn.server.alertsSummary !== 'Sending…'
                ? describeAlertsSent(checkIn.server.alertsSentAt, checkIn.server.alertsSummary ?? null)
                : 'Texting your Circle now…'}
            </Text>
            <Text style={styles.missedBody}>
              If you&apos;re OK, tap &quot;I&apos;m Safe&quot; and let them know yourself.
            </Text>
          </View>
        )}

        <Card style={styles.sessionCard}>
          <ThemedText type="smallBold" style={styles.cardTitle}>
            Active Session
          </ThemedText>

          <Text
            style={[styles.timer, { color: overdue ? Brand.red : theme.text }]}
            accessibilityLiveRegion="polite">
            {overdue ? `+${formatTimer(-msLeft)}` : formatTimer(msLeft)}
          </Text>
          <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
            {overdue ? 'Overdue · ' : ''}ETA {formatClock(checkIn.returnBy)}
          </ThemedText>
          {checkIn.destination && (
            <View style={styles.destinationRow}>
              <Ionicons name="location-outline" size={16} color={theme.textSecondary} />
              <ThemedText type="small" themeColor="textSecondary">
                {checkIn.destination}
              </ThemedText>
            </View>
          )}

          {/* -30m / +30m, hidden once your Circle was alerted. */}
          {!missed && (
            <View style={styles.adjustRow}>
              <BigButton
                label={`-${ADJUST_MINUTES}m`}
                variant="outline"
                size="small"
                disabled={adjusting || !canShorten}
                onPress={() => adjustBy(-ADJUST_MINUTES)}
              />
              <BigButton
                label={`+${ADJUST_MINUTES}m`}
                variant="outline"
                size="small"
                disabled={adjusting}
                onPress={() => adjustBy(ADJUST_MINUTES)}
              />
            </View>
          )}

          {overdue && !missed && (
            <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
              The server checks every minute and will alert your Circle shortly.
            </ThemedText>
          )}

          {/* What's really looking after you right now. */}
          <ThemedText type="small" themeColor="textSecondary" style={styles.monitoringLabel}>
            MONITORING
          </ThemedText>
          <View style={styles.chipRow}>
            <StatusChip
              icon="cloud-done-outline"
              label={!checkIn.server ? 'Server: not connected' : missed ? 'Server: missed' : 'Server watching'}
              ok={!!checkIn.server && !missed}
            />
            <StatusChip
              icon={remindersOn ? 'notifications-outline' : 'notifications-off-outline'}
              label={remindersOn ? 'Reminders on' : 'Reminders off'}
              ok={remindersOn === true}
            />
            {checkIn.shareLocation && (
              <StatusChip
                icon="location-outline"
                label={checkIn.locationShared ? 'Location shared' : 'Location: waiting'}
                ok={checkIn.locationShared}
              />
            )}
            {checkIn.photoUri && (
              <StatusChip
                icon="camera-outline"
                label={
                  checkIn.photoShared
                    ? 'Photo shared'
                    : checkIn.photoProblem
                      ? 'Photo not sent'
                      : 'Photo: sending…'
                }
                ok={checkIn.photoShared}
              />
            )}
          </View>
          {checkIn.photoProblem && (
            <Pressable onPress={retryPhoto} accessibilityRole="button">
              <ThemedText type="small" style={{ color: Brand.red }}>
                The outfit photo couldn&apos;t be sent ({checkIn.photoProblem}). Tap to retry.
              </ThemedText>
            </Pressable>
          )}

          <View style={styles.safeButton}>
            <BigButton label="I'm Safe" onPress={handleImSafe} />
          </View>
          <Pressable onPress={() => router.navigate('/check-in')} accessibilityRole="button">
            <ThemedText type="small" style={[styles.center, { color: Brand.green }]}>
              Change session details
            </ThemedText>
          </Pressable>
        </Card>

        {tipCard}
      </Screen>
    );
  }

  // ----- No active session -----
  return (
    <Screen title="">
      {header}
      <SosCard />

      <Card style={styles.sessionCard}>
        <ThemedText type="smallBold" style={styles.cardTitle}>
          Heading out?
        </ThemedText>
        <ThemedText themeColor="textSecondary">
          Set a time you expect to be back. If you don&apos;t check in by then, your Circle gets a
          text.
        </ThemedText>

        <View style={styles.circleRow}>
          <Ionicons name="people-circle-outline" size={22} color={Brand.green} />
          <ThemedText type="small" themeColor="textSecondary" style={styles.flex}>
            {contacts.length === 0
              ? 'Your Circle is empty. Add at least one trusted person.'
              : `Your Circle: ${contacts.map((c) => c.name).join(', ')}`}
          </ThemedText>
        </View>

        <View style={styles.safeButton}>
          <BigButton label="Start a session" onPress={() => router.navigate('/check-in')} />
        </View>
        {contacts.length === 0 && (
          <BigButton
            label="Add people to your Circle"
            variant="plain"
            onPress={() => router.navigate('/circle')}
          />
        )}

        <ThemedText
          type="small"
          style={[styles.center, { color: serverConnected ? Brand.green : Brand.red }]}>
          {serverConnected ? '● Connected' : '● Not connected to server'}
        </ThemedText>
      </Card>

      {tipCard}
    </Screen>
  );
}

// A small rounded status badge with an icon, e.g. "Server watching".
function StatusChip({
  icon,
  label,
  ok,
}: {
  icon: ComponentProps<typeof Ionicons>['name'];
  label: string;
  ok: boolean;
}) {
  const theme = useTheme();
  const color = ok ? Brand.green : Brand.red;
  return (
    <View style={[styles.chip, { backgroundColor: ok ? theme.backgroundSelected : '#FDECEC' }]}>
      <Ionicons name={icon} size={16} color={color} />
      <Text style={[styles.chipText, { color }]}>{label}</Text>
    </View>
  );
}

/**
 * Explains what the server actually sent after a missed check-in, based on
 * its summary ("Texted 1 of 1", "Texted 0 of 2 (…)", "No one in Circle").
 */
function describeAlertsSent(sentAt: string, summary: string | null) {
  const time = formatClock(new Date(sentAt));
  if (summary === 'No one in Circle') {
    return 'Your check-in was already missed, but your Circle is empty, so nobody was texted.';
  }
  const counts = summary?.match(/^Texted (\d+) of (\d+)/);
  if (counts && counts[1] === '0') {
    return `Your check-in was already missed at ${time}, but the alert texts couldn't be delivered. Nobody in your Circle was reached.`;
  }
  const sent = counts ? ` (texted ${counts[1]} of ${counts[2]})` : '';
  return `Your check-in was already missed, and your Circle was alerted at ${time}${sent}. Please let them know you're OK.`;
}

const styles = StyleSheet.create({
  destinationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.one,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: Spacing.three,
  },
  greeting: {
    fontWeight: 800,
  },
  sessionCard: {
    gap: Spacing.three,
  },
  cardTitle: {
    fontSize: 18,
    lineHeight: 24,
  },
  timer: {
    fontSize: 48,
    lineHeight: 56,
    fontWeight: 800,
    textAlign: 'center',
    fontVariant: ['tabular-nums'],
  },
  center: {
    textAlign: 'center',
  },
  adjustRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: Spacing.three,
  },
  monitoringLabel: {
    letterSpacing: 1,
    marginTop: Spacing.two,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.one,
    paddingVertical: Spacing.one + 2,
    paddingHorizontal: Spacing.three,
    borderRadius: 999,
  },
  chipText: {
    fontSize: 13,
    fontWeight: 600,
  },
  safeButton: {
    marginTop: Spacing.two,
  },
  circleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  flex: {
    flex: 1,
  },
  tipCard: {
    padding: Spacing.four,
    borderRadius: 22,
    gap: Spacing.two,
    opacity: 0.95,
  },
  tipTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  tipTitle: {
    fontSize: 16,
  },
  missedBanner: {
    backgroundColor: Brand.red,
    padding: Spacing.four,
    borderRadius: 22,
    gap: Spacing.one,
  },
  missedTitle: {
    color: Brand.onColor,
    fontSize: 18,
    fontWeight: 800,
  },
  missedBody: {
    color: Brand.onColor,
    fontSize: 14,
    lineHeight: 20,
  },
});
