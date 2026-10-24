import { DarkTheme, DefaultTheme, ThemeProvider, type ErrorBoundaryProps } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, useColorScheme } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import AppTabs from '@/components/app-tabs';
import { LoginScreen } from '@/components/login-screen';
import { WelcomeScreens } from '@/components/welcome-screens';
import { send as sendErrorReport, setUpErrorReporting } from '@/services/error-reporting';
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

/**
 * If a screen fails while drawing, show what went wrong (and a way back)
 * instead of the whole app closing. The error is also sent to the server.
 * Kept deliberately plain, so this screen itself can't fail.
 */
export function ErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  useEffect(() => {
    sendErrorReport(error, true);
  }, [error]);

  return (
    <ScrollView contentContainerStyle={errorStyles.page}>
      <Text style={errorStyles.title}>Something went wrong</Text>
      <Text style={errorStyles.body}>
        Your session and Circle are safe on the server. Tap below to go back.
      </Text>
      <Text selectable style={errorStyles.details}>
        {error.name}: {error.message}
      </Text>
      <Pressable onPress={retry} accessibilityRole="button" style={errorStyles.button}>
        <Text style={errorStyles.buttonText}>Try again</Text>
      </Pressable>
    </ScrollView>
  );
}

const errorStyles = StyleSheet.create({
  page: { flexGrow: 1, justifyContent: 'center', padding: 24, gap: 16, backgroundColor: '#0E1A24' },
  title: { color: '#FFFFFF', fontSize: 22, fontWeight: '700' },
  body: { color: '#C9D3DC', fontSize: 16 },
  details: { color: '#FFB4B4', fontSize: 13, fontFamily: 'monospace' },
  button: { backgroundColor: '#1F9D74', borderRadius: 14, paddingVertical: 14, alignItems: 'center' },
  buttonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '600' },
});
