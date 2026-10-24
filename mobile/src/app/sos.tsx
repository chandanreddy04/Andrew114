import { router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Alert, Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { BigButton } from '@/components/big-button';
import { Card } from '@/components/card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { getSosLocation, type SosLocation } from '@/services/location';
import type { SosResult } from '@/services/server';
import { useSafety } from '@/state/safety-store';
import { formatClock } from '@/utils/time';

// What the screen is doing right now.
type SosState =
  | { step: 'ready' }
  | { step: 'locating' }
  | {
      step: 'sent';
      at: Date;
      location: SosLocation | null;
      result: SosResult;
    };

/**
 * SOS: one big button that texts your whole Circle your location.
 * The texting happens on the server (backend/app/routers/sos.py).
 */
export default function SosScreen() {
  const { contacts, sendSos: sendSosToCircle } = useSafety();
  const [state, setState] = useState<SosState>({ step: 'ready' });

  async function sendSos() {
    if (contacts.length === 0) {
      Alert.alert('Your Circle is empty', 'Add at least one person so someone can be alerted.', [
        { text: 'Not now', style: 'cancel' },
        { text: 'Add people', onPress: () => router.navigate('/circle') },
      ]);
      return;
    }

    setState({ step: 'locating' });
    // Never let a location problem block the SOS: on any error, send without it.
    const location = await getSosLocation().catch(() => null);
    const result = await sendSosToCircle(location);
    setState({ step: 'sent', at: new Date(), location, result });
  }

  function handlePress() {
    // Ask first, so a pocket-tap doesn't send an alert by accident.
    Alert.alert('Send SOS?', 'Your Circle will be alerted right away with your location.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Send SOS', style: 'destructive', onPress: sendSos },
    ]);
  }

  return (
    <Screen title="SOS">
      <ThemedText themeColor="textSecondary">
        Feel unsafe? Press the button to alert your Circle with your location.
      </ThemedText>

      <View style={styles.center}>
        <Pressable
          onPress={handlePress}
          disabled={state.step === 'locating'}
          accessibilityRole="button"
          accessibilityLabel="Send SOS to your Circle"
          style={({ pressed }) => [styles.sosButton, pressed && styles.pressed]}>
          {state.step === 'locating' ? (
            <ActivityIndicator size="large" color={Brand.onYellow} />
          ) : (
            <Text style={styles.sosText}>SOS</Text>
          )}
        </Pressable>
      </View>

      {state.step === 'ready' && (
        <ThemedText type="small" themeColor="textSecondary" style={styles.note}>
          {contacts.length === 0
            ? 'Your Circle is empty. Add people on the Circle tab.'
            : `Will alert: ${contacts.map((c) => c.name).join(', ')}`}
        </ThemedText>
      )}

      {state.step === 'locating' && (
        <ThemedText type="small" themeColor="textSecondary" style={styles.note}>
          Getting your location…
        </ThemedText>
      )}

      {state.step === 'sent' && <SentCard state={state} onDone={() => setState({ step: 'ready' })} />}
    </Screen>
  );
}

/** Shows what happened: who was texted, when, and where you were. */
function SentCard({
  state,
  onDone,
}: {
  state: Extract<SosState, { step: 'sent' }>;
  onDone: () => void;
}) {
  const { location, result } = state;
  const allSent = result.ok && result.total > 0 && result.sent === result.total;

  return (
    <Card>
      {result.ok ? (
        <>
          <ThemedText type="smallBold" style={{ color: allSent ? Brand.green : Brand.red }}>
            SOS at {formatClock(state.at)}: texted {result.sent} of {result.total}{' '}
            {result.total === 1 ? 'person' : 'people'}
          </ThemedText>
          {result.trialTemplate && (
            <ThemedText type="small" themeColor="textSecondary">
              Test mode: Twilio is on a trial account, so a generic Twilio sample text was sent
              instead of your SOS message and location.
            </ThemedText>
          )}
          {result.errors.map((error) => (
            <ThemedText key={error} type="small" style={{ color: Brand.red }}>
              ✗ {error}
            </ThemedText>
          ))}
        </>
      ) : (
        <ThemedText type="smallBold" style={{ color: Brand.red }}>
          SOS could not be sent: {result.error}
        </ThemedText>
      )}

      {!allSent && (
        <ThemedText type="small" style={{ color: Brand.red }}>
          If you are in danger, call your local emergency number or someone you trust directly.
        </ThemedText>
      )}

      {location ? (
        <>
          <ThemedText type="small">
            📍 {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}
            {location.accuracyMeters !== null && ` (±${Math.round(location.accuracyMeters)} m)`}
          </ThemedText>
          {location.isApproximate && (
            <ThemedText type="small" themeColor="textSecondary">
              GPS was slow, so this is your last known location.
            </ThemedText>
          )}
          <BigButton
            label="Open in Maps"
            variant="plain"
            onPress={() => Linking.openURL(location.mapsUrl)}
          />
        </>
      ) : (
        <ThemedText type="small" style={{ color: Brand.red }}>
          Location unavailable. Location permission was refused, or no GPS signal. Your Circle
          would still be alerted.
        </ThemedText>
      )}

      <BigButton label="Done" onPress={onDone} />
    </Card>
  );
}

const SIZE = 200;

const styles = StyleSheet.create({
  center: {
    alignItems: 'center',
    paddingVertical: Spacing.five,
  },
  sosButton: {
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    backgroundColor: Brand.yellow,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 6,
    borderColor: '#FFFFFF',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.18)',
  },
  pressed: {
    transform: [{ scale: 0.95 }],
    opacity: 0.85,
  },
  sosText: {
    color: Brand.onYellow,
    fontSize: 48,
    fontWeight: 800,
    letterSpacing: 2,
  },
  note: {
    textAlign: 'center',
  },
});
