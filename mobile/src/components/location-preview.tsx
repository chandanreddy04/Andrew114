import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Platform, Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { addressAt, getSosLocation, isLocationAllowed } from '@/services/location';
import { fetchMapPreview } from '@/services/server';

// The map image's shape (the server is asked for this size).
const MAP_ASPECT = 720 / 336;
const PIN = 36;

type State =
  | { kind: 'loading' }
  | { kind: 'denied' }
  | { kind: 'failed' }
  | { kind: 'found'; map: string | null; address: string | null; approximate: boolean };

/**
 * Under the Location switch on Start Session: a small map of where the phone
 * is now, so you can see what your Circle would get. Only shown while the
 * switch is on; the map is drawn when it appears and when you tap refresh.
 */
export function LocationPreview() {
  const theme = useTheme();
  const [state, setState] = useState<State>({ kind: 'loading' });

  const locate = useCallback(async () => {
    setState({ kind: 'loading' });
    const location = await getSosLocation().catch(() => null);
    if (!location) {
      setState({ kind: (await isLocationAllowed()) ? 'failed' : 'denied' });
      return;
    }
    const [map, address] = await Promise.all([
      fetchMapPreview(location),
      addressAt(location.latitude, location.longitude),
    ]);
    setState({ kind: 'found', map, address, approximate: location.isApproximate });
  }, []);

  useEffect(() => {
    // Not awaited: the preview fills in when the location arrives.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    locate();
  }, [locate]);

  const box = { backgroundColor: theme.backgroundElement, borderColor: theme.border };

  if (state.kind === 'denied' || state.kind === 'failed') {
    return (
      <View style={[styles.box, styles.message, box]}>
        <Ionicons name="location-outline" size={22} color={theme.textSecondary} />
        <View style={styles.messageText}>
          <ThemedText type="small" themeColor="textSecondary">
            {state.kind === 'denied'
              ? "Androyit isn't allowed to use your location, so it can't be shared."
              : "Couldn't find your location. Check that location is on."}
          </ThemedText>
          <Pressable
            onPress={() =>
              state.kind === 'denied' && Platform.OS !== 'web' ? Linking.openSettings() : locate()
            }
            accessibilityRole="button"
            hitSlop={Spacing.two}>
            <ThemedText type="smallBold" style={{ color: Brand.green }}>
              {state.kind === 'denied' ? 'Open Settings' : 'Try again'}
            </ThemedText>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.box, box]}>
      <View style={[styles.map, { backgroundColor: theme.backgroundSelected }]}>
        {state.kind === 'found' && state.map ? (
          <>
            <Image
              source={{ uri: state.map }}
              style={StyleSheet.absoluteFill}
              contentFit="cover"
              accessibilityLabel="Map of your current location"
            />
            {/* The pin's tip sits on the middle of the map, where you are. */}
            <View pointerEvents="none" style={styles.pin}>
              <Ionicons name="location" size={PIN} color={Brand.green} />
            </View>
          </>
        ) : state.kind === 'loading' ? (
          <ActivityIndicator color={Brand.green} />
        ) : (
          <Ionicons name="map-outline" size={32} color={theme.textSecondary} />
        )}
      </View>
      <View style={styles.footer}>
        <View style={styles.footerText}>
          <ThemedText type="smallBold">Your current location</ThemedText>
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>
            {state.kind === 'loading'
              ? 'Finding you…'
              : (state.address ?? 'Location found') +
                (state.approximate ? ' (approximate)' : '')}
          </ThemedText>
        </View>
        <Pressable
          onPress={locate}
          disabled={state.kind === 'loading'}
          accessibilityRole="button"
          accessibilityLabel="Refresh your location"
          hitSlop={Spacing.two}>
          <Ionicons name="refresh" size={22} color={Brand.green} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    borderRadius: 24,
    borderWidth: 1,
    overflow: 'hidden',
  },
  map: {
    width: '100%',
    aspectRatio: MAP_ASPECT,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pin: {
    position: 'absolute',
    left: '50%',
    top: '50%',
    marginLeft: -PIN / 2,
    marginTop: -PIN,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.four,
  },
  footerText: {
    flex: 1,
  },
  message: {
    flexDirection: 'row',
    gap: Spacing.three,
    padding: Spacing.four,
  },
  messageText: {
    flex: 1,
    gap: Spacing.two,
  },
});
