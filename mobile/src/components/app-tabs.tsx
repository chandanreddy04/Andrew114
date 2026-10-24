import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';
import { type ComponentProps } from 'react';
import {
  type ColorValue,
  type GestureResponderEvent,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Brand } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

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
          tabBarButton: (props) => <SosTabButton onPress={props.onPress ?? undefined} />,
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
    </Tabs>
  );
}

const SOS_SIZE = 72;

// The big round yellow SOS button in the middle of the tab bar.
function SosTabButton({ onPress }: { onPress?: (e: GestureResponderEvent) => void }) {
  return (
    <View style={styles.sosSlot}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel="SOS"
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
