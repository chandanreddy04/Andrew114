import { DarkTheme, DefaultTheme, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useColorScheme } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import AppTabs from '@/components/app-tabs';
import { LoginScreen } from '@/components/login-screen';
import { WelcomeScreens } from '@/components/welcome-screens';
import { setUpErrorReporting } from '@/services/error-reporting';
import { SafetyProvider, useSafety } from '@/state/safety-store';

SplashScreen.preventAutoHideAsync();
setUpErrorReporting();

export default function TabLayout() {
  const colorScheme = useColorScheme();
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      {/* SafetyProvider shares login, check-in and contacts with every screen. */}
      <SafetyProvider>
        <AnimatedSplashOverlay />
        <LoginGate />
      </SafetyProvider>
    </ThemeProvider>
  );
}

// Logged in: show the tabs. Logged out: show the welcome pages the first
// time on this phone, then the login screen.
function LoginGate() {
  const { loggedInPhone, welcomeSeen, markWelcomeSeen } = useSafety();
  if (loggedInPhone) return <AppTabs />;
  if (!welcomeSeen) return <WelcomeScreens onDone={markWelcomeSeen} />;
  return <LoginScreen />;
}
