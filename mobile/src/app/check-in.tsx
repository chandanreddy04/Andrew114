import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  Alert,
  Platform,
  Pressable,
  StyleSheet,
  Switch,
  TextInput,
  View,
} from 'react-native';

import { BigButton } from '@/components/big-button';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { askNotificationPermission } from '@/services/notifications';
import { choosePhoto } from '@/services/photos';
import { useSafety } from '@/state/safety-store';
import { inShownOrder } from '@/utils/alert';
import { formatClock } from '@/utils/time';

// The - and + buttons move the return time by this many minutes.
const STEP_MINUTES = 15;
// The earliest return time allowed, and the latest (from now).
const MIN_AHEAD_MINUTES = 5;
const MAX_AHEAD_MINUTES = 12 * 60;
// A 1-minute test session appears only while developing (__DEV__) and in test
// builds (EXPO_PUBLIC_TEST_OPTIONS=1 in the EAS "preview" environment), never
// in the real app, where such a short session would cause false alarms.
const SHOW_TEST_OPTIONS = __DEV__ || process.env.EXPO_PUBLIC_TEST_OPTIONS === '1';

const MINUTE = 60 * 1000;

// One hour from now, rounded up to the next quarter hour (e.g. 2:09 -> 3:15).
function defaultReturnTime() {
  const quarter = STEP_MINUTES * MINUTE;
  return new Date(Math.ceil((Date.now() + 60 * MINUTE) / quarter) * quarter);
}

/**
 * Start Session (or change the one that's going): where you're going, when
 * you'll be back, an outfit photo, and whether to share your location. The
 * details are only shown to your Circle if an alert triggers.
 */
export default function CheckInScreen() {
  const { checkIn, startCheckIn, contacts } = useSafety();
  const theme = useTheme();

  const [destination, setDestination] = useState(checkIn?.destination ?? '');
  const [returnBy, setReturnBy] = useState(() => checkIn?.returnBy ?? defaultReturnTime());
  const [photoUri, setPhotoUri] = useState<string | null>(checkIn?.photoUri ?? null);
  const [shareLocation, setShareLocation] = useState(checkIn?.shareLocation ?? true);
  const [starting, setStarting] = useState(false);

  // The current time, refreshed every 30 seconds, so the - button knows how
  // early the return time may be.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30 * 1000);
    return () => clearInterval(timer);
  }, []);

  const earliest = now + MIN_AHEAD_MINUTES * MINUTE;
  const latest = now + MAX_AHEAD_MINUTES * MINUTE;
  const canEarlier = returnBy.getTime() - STEP_MINUTES * MINUTE >= earliest;
  const canLater = returnBy.getTime() + STEP_MINUTES * MINUTE <= latest;

  function moveBy(minutes: number) {
    setReturnBy((current) => {
      const next = current.getTime() + minutes * MINUTE;
      return new Date(Math.min(latest, Math.max(earliest, next)));
    });
  }

  async function pickPhoto(source: 'camera' | 'library') {
    const result = await choosePhoto(source);
    if (result.kind === 'picked') setPhotoUri(result.uri);
    else if (result.kind === 'denied') {
      Alert.alert(
        source === 'camera' ? 'Camera not allowed' : 'Photos not allowed',
        "You can allow it for Androyit in your phone's Settings, or skip the photo.",
      );
    } else if (result.kind === 'error') {
      Alert.alert("Couldn't get the photo", result.message);
    }
  }

  // Where the photo comes from.
  function choosePhotoSource() {
    // Alert buttons don't work in the web preview; there, open the file picker.
    if (Platform.OS === 'web') return pickPhoto('library');
    Alert.alert(
      photoUri ? 'Change photo' : 'Outfit photo',
      'Shown to your Circle only if an alert triggers.',
      inShownOrder([
        { text: 'Take photo', onPress: () => pickPhoto('camera') },
        { text: 'Choose from gallery', onPress: () => pickPhoto('library') },
        { text: 'Cancel', style: 'cancel' },
      ]),
      { cancelable: true },
    );
  }

  // Tapping the photo box: add a photo, or change / remove the one there.
  function handlePhotoPress() {
    if (!photoUri || Platform.OS === 'web') return choosePhotoSource();
    Alert.alert(
      'Outfit photo',
      'Shown to your Circle only if an alert triggers.',
      inShownOrder([
        { text: 'Change photo', onPress: choosePhotoSource },
        { text: 'Remove photo', style: 'destructive', onPress: () => setPhotoUri(null) },
        { text: 'Cancel', style: 'cancel' },
      ]),
      { cancelable: true },
    );
  }

  async function start(time: Date) {
    setStarting(true);
    // Ask for notification permission first, so the reminders can be scheduled.
    const allowed = await askNotificationPermission();

    const original = checkIn?.photoUri ?? null;
    const savedToServer = await startCheckIn(time, {
      destination: destination.trim(),
      shareLocation,
      // Only send the photo when it's new (or removed).
      photo: photoUri !== original ? photoUri : undefined,
    });
    setStarting(false);
    router.navigate('/'); // go back to Home to see the countdown

    // Tell the user plainly about anything that isn't fully working.
    const problems: string[] = [];
    if (!savedToServer) {
      problems.push(
        "The server couldn't be reached, so if your phone dies nobody will notice. Check your internet; the app will retry next time it opens.",
      );
    }
    if (!allowed && Platform.OS !== 'web') {
      problems.push(
        "You won't get a reminder before your time is up. You can turn notifications on for Androyit in your phone's Settings.",
      );
    }
    if (problems.length > 0) {
      Alert.alert('Session started, but…', problems.join('\n\n'));
    }
  }

  function handleStart(time: Date = returnBy) {
    if (time.getTime() <= Date.now() + 30 * 1000) {
      Alert.alert('That time has passed', 'Pick a later return time.');
      return;
    }
    // Warn if nobody would be alerted.
    if (contacts.length === 0) {
      Alert.alert('Your Circle is empty', 'Nobody would be alerted if you miss this check-in.', [
        { text: 'Add people', onPress: () => router.navigate('/circle') },
        { text: 'Start anyway', style: 'destructive', onPress: () => start(time) },
      ]);
      return;
    }
    start(time);
  }

  const field = { backgroundColor: theme.backgroundElement, borderColor: theme.border };

  return (
    <Screen title="">
      {/* Header: back to Home, and the title in the middle. */}
      <View style={styles.header}>
        <Pressable
          onPress={() => router.navigate('/')}
          accessibilityRole="button"
          accessibilityLabel="Back to Home"
          hitSlop={Spacing.three}
          style={styles.headerSide}>
          <Ionicons name="arrow-back" size={26} color={theme.text} />
        </Pressable>
        <ThemedText type="smallBold" style={styles.headerTitle}>
          {checkIn ? 'Change Session' : 'Start Session'}
        </ThemedText>
        <View style={styles.headerSide} />
      </View>

      {/* Where are you going? */}
      <View style={styles.section}>
        <ThemedText type="smallBold" style={styles.label}>
          Where are you going?
        </ThemedText>
        <View style={[styles.pill, styles.inputPill, field]}>
          <Ionicons name="location-outline" size={22} color={theme.textSecondary} />
          <TextInput
            value={destination}
            onChangeText={setDestination}
            placeholder="e.g. Central Park"
            placeholderTextColor={theme.textSecondary}
            maxLength={120}
            returnKeyType="done"
            style={[styles.input, { color: theme.text }]}
          />
        </View>
      </View>

      {/* When will you be back? */}
      <View style={styles.section}>
        <ThemedText type="smallBold" style={styles.label}>
          When will you be back?
        </ThemedText>
        <View style={styles.timeRow}>
          <Pressable
            onPress={() => moveBy(-STEP_MINUTES)}
            disabled={!canEarlier}
            accessibilityRole="button"
            accessibilityLabel={`${STEP_MINUTES} minutes earlier`}
            style={[styles.round, field, !canEarlier && styles.dimmed]}>
            <Ionicons name="remove" size={28} color={theme.text} />
          </Pressable>
          <View style={[styles.pill, styles.timePill, field]}>
            <ThemedText style={styles.time}>{formatClock(returnBy)}</ThemedText>
          </View>
          <Pressable
            onPress={() => moveBy(STEP_MINUTES)}
            disabled={!canLater}
            accessibilityRole="button"
            accessibilityLabel={`${STEP_MINUTES} minutes later`}
            style={[styles.round, field, !canLater && styles.dimmed]}>
            <Ionicons name="add" size={28} color={theme.text} />
          </Pressable>
        </View>
        {SHOW_TEST_OPTIONS && !checkIn && (
          <Pressable
            onPress={() => handleStart(new Date(Date.now() + MINUTE))}
            accessibilityRole="button"
            style={styles.testLink}>
            <ThemedText type="small" style={{ color: Brand.green }}>
              Test: start a 1-minute session
            </ThemedText>
          </Pressable>
        )}
      </View>

      {/* Outfit photo */}
      <View style={styles.section}>
        <ThemedText type="smallBold" style={styles.label}>
          Outfit photo
        </ThemedText>
        <Pressable
          onPress={handlePhotoPress}
          accessibilityRole="button"
          accessibilityLabel={photoUri ? 'Change outfit photo' : 'Add outfit photo'}
          style={[styles.photoBox, { borderColor: theme.border }]}>
          {photoUri ? (
            <>
              <Image source={{ uri: photoUri }} style={styles.photo} contentFit="cover" />
              <View style={styles.photoBadge}>
                <Ionicons name="camera-outline" size={16} color={Brand.onColor} />
                <ThemedText type="small" style={{ color: Brand.onColor }}>
                  Change
                </ThemedText>
              </View>
            </>
          ) : (
            <>
              <Ionicons name="camera-outline" size={40} color={theme.textSecondary} />
              <ThemedText themeColor="textSecondary">Add Photo</ThemedText>
            </>
          )}
        </Pressable>
      </View>

      {/* Sharing options */}
      <View style={styles.section}>
        <ThemedText type="smallBold" style={styles.label}>
          Sharing options
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Shared with your Circle if an alert triggers
        </ThemedText>
        <View style={[styles.pill, styles.switchRow, field]}>
          <Ionicons name="location-outline" size={22} color={theme.textSecondary} />
          <ThemedText style={styles.switchLabel}>Location</ThemedText>
          <Switch
            value={shareLocation}
            onValueChange={setShareLocation}
            trackColor={{ false: theme.border, true: Brand.green }}
            thumbColor="#FFFFFF"
            accessibilityLabel="Share my location if an alert triggers"
          />
        </View>
      </View>

      <ThemedText type="small" themeColor="textSecondary" style={styles.note}>
        Session data is deleted 7 days after your session ends. Extend or review it anytime in
        Session History.
      </ThemedText>

      <BigButton
        label={starting ? 'Starting…' : checkIn ? 'Update session' : 'Start session'}
        onPress={() => handleStart()}
        disabled={starting}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerSide: {
    width: 32,
  },
  headerTitle: {
    fontSize: 20,
    lineHeight: 26,
  },
  section: {
    gap: Spacing.two,
  },
  label: {
    fontSize: 18,
    lineHeight: 24,
  },
  pill: {
    borderRadius: 999,
    borderWidth: 1,
    minHeight: 60,
    paddingHorizontal: Spacing.four,
    flexDirection: 'row',
    alignItems: 'center',
  },
  inputPill: {
    gap: Spacing.three,
  },
  input: {
    flex: 1,
    fontSize: 18,
    paddingVertical: Spacing.three,
  },
  timeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
  },
  round: {
    width: 60,
    height: 60,
    borderRadius: 30,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  timePill: {
    flex: 1,
    justifyContent: 'center',
  },
  time: {
    fontSize: 22,
    lineHeight: 30,
    fontWeight: 600,
  },
  dimmed: {
    opacity: 0.4,
  },
  testLink: {
    alignSelf: 'center',
    paddingVertical: Spacing.one,
  },
  photoBox: {
    height: 240,
    borderRadius: 22,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
    overflow: 'hidden',
  },
  photo: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  photoBadge: {
    position: 'absolute',
    right: Spacing.three,
    bottom: Spacing.three,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.one,
    backgroundColor: 'rgba(0, 0, 0, 0.55)',
    borderRadius: 999,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.one,
  },
  switchRow: {
    gap: Spacing.three,
  },
  switchLabel: {
    flex: 1,
    fontSize: 18,
  },
  note: {
    textAlign: 'center',
  },
});
