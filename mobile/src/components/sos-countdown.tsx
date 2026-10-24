import { useEffect, useState } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';

import { Brand } from '@/constants/theme';
import { useSafety } from '@/state/safety-store';

/**
 * "Notifying your circle of trust in 3… 2… 1…", drawn over every screen while
 * the SOS button is held. It doesn't take touches (pointerEvents none), so
 * your finger stays on the button and letting go still cancels.
 */
export function SosCountdownOverlay() {
  const { sosCountdown } = useSafety();
  // One animated value for the whole life of the overlay.
  const [pulse] = useState(() => new Animated.Value(0));

  const showing = sosCountdown !== null;
  useEffect(() => {
    if (!showing) return;
    pulse.setValue(0);
    const loop = Animated.loop(
      Animated.timing(pulse, {
        toValue: 1,
        duration: 1000,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [showing, pulse]);

  if (!showing) return null;

  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.85, 1.1] });
  const opacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 0.7] });

  return (
    <View pointerEvents="none" style={styles.overlay} accessibilityLiveRegion="assertive">
      <Animated.View style={[styles.circle, { transform: [{ scale }], opacity }]} />
      <View style={styles.texts}>
        <Text style={styles.caption}>Notifying your circle of trust in</Text>
        <Text style={styles.number}>{sosCountdown}</Text>
      </View>
    </View>
  );
}

const CIRCLE = 320;

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 1000,
    elevation: 1000,
    // Light, see-through grey over the screen; the pulsing circle is yellow.
    backgroundColor: 'rgba(225, 228, 232, 0.78)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  circle: {
    position: 'absolute',
    width: CIRCLE,
    height: CIRCLE,
    borderRadius: CIRCLE / 2,
    backgroundColor: Brand.yellow,
  },
  texts: {
    alignItems: 'center',
    gap: 8,
  },
  caption: {
    color: '#2C3E50', // dark navy: readable on the grey and on the yellow
    fontSize: 22,
    fontWeight: 700,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  number: {
    color: '#FFFFFF',
    fontSize: 140,
    lineHeight: 160,
    fontWeight: 800,
    textShadowColor: 'rgba(0, 0, 0, 0.35)',
    textShadowOffset: { width: 0, height: 4 },
    textShadowRadius: 10,
  },
});
