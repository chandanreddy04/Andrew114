import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { type ComponentProps, useEffect, useState } from 'react';
import { Alert, Linking, StyleSheet, Text, View } from 'react-native';

import { BigButton } from '@/components/big-button';
import { Card } from '@/components/card';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSafety } from '@/state/safety-store';
import { formatTimer } from '@/utils/time';

/**
 * "Emergency SOS" on Home after you held the SOS button: whether your Circle
 * was texted, how long ago, what's being shared, and "I'm Safe".
 */
export function SosCard() {
  const { activeSos, endSos, triggerSos, contacts } = useSafety();
  const [ending, setEnding] = useState(false);

  // Counts up every second.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  if (!activeSos) return null;
  const { status, result } = activeSos;

  async function handleSafe() {
    setEnding(true);
    const outcome = await endSos();
    setEnding(false);
    if (!outcome.reached) {
      Alert.alert("Couldn't reach the server", `${outcome.error}\n\nPlease tell your Circle you're OK yourself.`);
    } else if (outcome.allClearSent) {
      Alert.alert("Glad you're safe", "We've texted your Circle that you're OK.");
    } else {
      Alert.alert("Glad you're safe", 'Your SOS has ended.');
    }
  }

  let statusText: string;
  let statusColor: string = Brand.red;
  if (status === 'sending') statusText = 'Sending…';
  else if (!result || !result.ok) statusText = `Couldn't send: ${result && !result.ok ? result.error : 'unknown error'}`;
  else if (result.total === 0) statusText = 'No one in your Circle to alert';
  else {
    statusText = `Circle notified · texted ${result.sent} of ${result.total}`;
    if (result.sent === result.total) statusColor = Brand.green;
  }

  const failed = status === 'failed' || (result?.ok && result.sent === 0);

  return (
    <Card style={[styles.card, { borderLeftColor: Brand.red }]}>
      <ThemedText type="smallBold" style={styles.title}>
        Emergency SOS
      </ThemedText>
      <Text style={[styles.status, { color: statusColor }]}>{statusText}</Text>
      <Text style={styles.timer} accessibilityLabel="Time since SOS">
        +{formatTimer(now - activeSos.startedAt.getTime())}
      </Text>
      {result?.ok && result.trialTemplate && (
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          Twilio trial: a sample text was sent instead of your SOS message.
        </ThemedText>
      )}

      <ThemedText type="small" themeColor="textSecondary" style={styles.sharingLabel}>
        SHARING WITH YOUR CIRCLE
      </ThemedText>
      <View style={styles.iconRow}>
        <ShareIcon
          icon="location"
          on={activeSos.hadLocation}
          label={activeSos.hadLocation ? 'Location shared' : 'Location not available'}
        />
        <ShareIcon
          icon={batteryIcon(activeSos.batteryPercent)}
          on={activeSos.batteryPercent !== null}
          label={
            activeSos.batteryPercent !== null ? `Battery ${activeSos.batteryPercent}%` : 'Battery not shared'
          }
          text={activeSos.batteryPercent !== null ? `${activeSos.batteryPercent}%` : undefined}
        />
        <ShareIcon
          icon="camera"
          on={activeSos.photoShared}
          label={activeSos.photoShared ? 'Outfit photo shared' : 'No outfit photo'}
        />
      </View>

      {failed && (
        <View style={styles.help}>
          <ThemedText type="small" style={{ color: Brand.red }}>
            If you are in danger, call your local emergency number or someone you trust directly.
          </ThemedText>
          {contacts.length === 0 ? (
            <BigButton label="Add people to your Circle" variant="plain" onPress={() => router.navigate('/circle')} />
          ) : (
            status === 'failed' && <BigButton label="Try sending again" variant="plain" onPress={triggerSos} />
          )}
          <BigButton label="Call emergency services" variant="danger" onPress={() => Linking.openURL('tel:911')} />
        </View>
      )}

      <BigButton
        label={ending ? 'Please wait…' : "I'm Safe"}
        onPress={handleSafe}
        disabled={ending || status === 'sending'}
      />
    </Card>
  );
}

function batteryIcon(percent: number | null): ComponentProps<typeof Ionicons>['name'] {
  if (percent === null) return 'battery-dead-outline';
  if (percent <= 20) return 'battery-dead';
  if (percent <= 60) return 'battery-half';
  return 'battery-full';
}

function ShareIcon({
  icon,
  on,
  label,
  text,
}: {
  icon: ComponentProps<typeof Ionicons>['name'];
  on: boolean;
  label: string;
  text?: string;
}) {
  const theme = useTheme();
  const color = on ? Brand.green : theme.textSecondary;
  return (
    <View
      accessible
      accessibilityLabel={label}
      style={[styles.icon, { backgroundColor: on ? theme.backgroundSelected : theme.background }]}>
      <Ionicons name={icon} size={18} color={color} />
      {text && <Text style={[styles.iconText, { color }]}>{text}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderLeftWidth: 5,
  },
  title: {
    fontSize: 20,
    lineHeight: 26,
  },
  status: {
    textAlign: 'center',
    fontSize: 18,
    fontWeight: 700,
    marginTop: Spacing.two,
  },
  timer: {
    textAlign: 'center',
    fontSize: 44,
    fontWeight: 800,
    color: Brand.red,
    fontVariant: ['tabular-nums'],
  },
  center: {
    textAlign: 'center',
  },
  sharingLabel: {
    letterSpacing: 1,
    marginTop: Spacing.two,
  },
  iconRow: {
    flexDirection: 'row',
    gap: Spacing.two,
    marginBottom: Spacing.two,
  },
  icon: {
    minWidth: 44,
    height: 36,
    borderRadius: 18,
    paddingHorizontal: Spacing.two,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  iconText: {
    fontSize: 13,
    fontWeight: 700,
  },
  help: {
    gap: Spacing.two,
    marginBottom: Spacing.two,
  },
});
