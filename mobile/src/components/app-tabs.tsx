import Ionicons from '@expo/vector-icons/Ionicons';
import { router, Tabs } from 'expo-router';
import { type ComponentProps, useEffect, useRef } from 'react';
import {
  type ColorValue,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  ToastAndroid,
  Vibration,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Brand } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSafety } from '@/state/safety-store';

type IconName = ComponentProps<typeof Ionicons>['name'];

// A tab icon: filled when the tab is selected, outlined otherwise.
function tabIcon(filled: IconName, outline: IconName) {
  function TabIcon({ color, focused }: { color: ColorValue; focused: boolean }) {
    return <Ionicons name={focused ? filled : outline} size={26} color={color as string} />;
  }
  return TabIcon;
}

/**
 * The bottom tab bar: Home · Circle · (SOS) · Notifications · Settings.
 * SOS is a round yellow button raised above the bar. Check-in and Session
 * History are screens too, but opened from Home and Settings instead of tabs.
 * Each <Tabs.Screen name="..."> matches a file in src/app/.
 */
export default function AppTabs() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  return (
    <Tabs
      screenOptions={{
        headerShown: false, // each screen draws its own title
        tabBarShowLabel: false, // icons only, like the design
        tabBarActiveTintColor: Brand.green,
        tabBarInactiveTintColor: theme.textSecondary,
        tabBarStyle: {
          backgroundColor: theme.backgroundElement,
          borderTopColor: theme.border,
          height: 64 + insets.bottom,
          paddingTop: 8,
        },
      }}>
      <Tabs.Screen
        name="index"
        options={{ title: 'Home', tabBarIcon: tabIcon('home', 'home-outline') }}
      />
      <Tabs.Screen
        name="circle"
        options={{ title: 'Circle', tabBarIcon: tabIcon('people-circle', 'people-circle-outline') }}
      />
      <Tabs.Screen
        name="sos"
        options={{
          title: 'SOS',
          // Not a page: holding the button sends the SOS from any screen.
          tabBarButton: () => <SosTabButton />,
        }}
      />
      <Tabs.Screen
        name="notifications"
        options={{
          title: 'Notifications',
          tabBarIcon: tabIcon('notifications', 'notifications-outline'),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: 'Settings', tabBarIcon: tabIcon('settings', 'settings-outline') }}
      />

      {/* Real screens, but not shown as tabs. */}
      <Tabs.Screen name="check-in" options={{ href: null }} />
      <Tabs.Screen name="history" options={{ href: null }} />
      {/* Edit Profile fills the screen, like the design (no tab bar). */}
      <Tabs.Screen
        name="edit-profile"
        options={{ href: null, tabBarStyle: { display: 'none' } }}
      />
    </Tabs>
  );
}

const SOS_SIZE = 72;

const HOLD_SECONDS = 3;

function toast(message: string) {
  if (Platform.OS === 'android') ToastAndroid.show(message, ToastAndroid.SHORT);
}

/**
 * The big round yellow SOS button in the middle of the tab bar. Hold it for
 * 3 seconds (it buzzes each second, with a countdown over the screen) and
 * your Circle is alerted. Letting go earlier cancels, so a pocket tap never
 * sends one.
 */
function SosTabButton() {
  const { activeSos, triggerSos, setSosCountdown } = useSafety();
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const pressedAt = useRef(0);
  const fired = useRef(false);

  function stopTimer() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }
  // Never leave the countdown running if the button goes away.
  useEffect(() => () => stopTimer(), []);

  function fire() {
    stopTimer();
    fired.current = true;
    setSosCountdown(null);
    Vibration.vibrate(500);
    router.navigate('/'); // Home shows the SOS card
    triggerSos();
  }

  function handlePressIn() {
    fired.current = false;
    pressedAt.current = Date.now();
    if (activeSos && activeSos.status !== 'failed') return; // already sent; see handlePressOut
    let left = HOLD_SECONDS;
    setSosCountdown(left);
    Vibration.vibrate(60);
    stopTimer();
    timer.current = setInterval(() => {
      left -= 1;
      if (left > 0) {
        setSosCountdown(left);
        Vibration.vibrate(60);
      } else {
        fire();
      }
    }, 1000);
  }

  function handlePressOut() {
    if (fired.current) return;
    stopTimer();
    setSosCountdown(null);
    if (activeSos && activeSos.status !== 'failed') {
      router.navigate('/');
      toast('SOS is active. Tap "I\'m Safe" on Home when you\'re OK.');
    } else if (Date.now() - pressedAt.current < 800) {
      toast('Hold SOS for 3 seconds to alert your Circle');
    }
  }

  return (
    <View style={styles.sosSlot}>
      <Pressable
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        accessibilityRole="button"
        accessibilityLabel="SOS"
        accessibilityHint="Hold for 3 seconds to alert your Circle with your location"
        // Screen readers: double-tap "activate" sends it straight away.
        accessibilityActions={[{ name: 'activate', label: 'Send SOS' }]}
        onAccessibilityAction={(event) => event.nativeEvent.actionName === 'activate' && fire()}
        style={({ pressed }) => [styles.sosButton, pressed && styles.sosPressed]}>
        <Text style={styles.sosText}>SOS</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  sosSlot: {
    flex: 1,
    alignItems: 'center',
  },
  sosButton: {
    width: SOS_SIZE,
    height: SOS_SIZE,
    borderRadius: SOS_SIZE / 2,
    marginTop: -SOS_SIZE / 2, // raised: half of it sticks up above the bar
    backgroundColor: Brand.yellow,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 4,
    borderColor: '#FFFFFF',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.18)',
  },
  sosPressed: {
    transform: [{ scale: 0.94 }],
  },
  sosText: {
    color: Brand.onYellow,
    fontSize: 20,
    fontWeight: 800,
    letterSpacing: 1,
  },
});
