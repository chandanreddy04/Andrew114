import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Platform, Pressable, StyleSheet } from 'react-native';

import { appVersionText } from '@/components/app-version';
import { ProfileHeader } from '@/components/profile-header';
import { Screen } from '@/components/screen';
import { SettingsRow, SettingsSection } from '@/components/settings-list';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useSafety } from '@/state/safety-store';

/**
 * Settings: your name and number, subscription (coming soon), session history, the
 * "About" links, delete account, and a Log out button at the very bottom.
 */
export default function SettingsScreen() {
  const { logOut, deleteAccount, checkIn } = useSafety();
  const [busy, setBusy] = useState(false);

  // Alert buttons don't work in the web preview, so there we skip the question.
  function confirm(title: string, message: string, action: string, onYes: () => void) {
    if (Platform.OS === 'web') return onYes();
    Alert.alert(title, message, [
      { text: 'Cancel', style: 'cancel' },
      { text: action, style: 'destructive', onPress: onYes },
    ]);
  }

  async function handleLogOut() {
    setBusy(true);
    const problem = await logOut();
    setBusy(false);
    if (problem) Alert.alert("Can't log out yet", problem);
  }

  async function handleDelete() {
    setBusy(true);
    const problem = await deleteAccount();
    setBusy(false);
    if (problem) Alert.alert("Couldn't delete your account", problem);
  }

  return (
    <Screen title="">
      <ProfileHeader />

      <SettingsSection title="Subscription">
        <SettingsRow icon="card-outline" title="Manage Subscription" comingSoon />
        <SettingsRow icon="gift-outline" title="Refer a Friend" comingSoon last />
      </SettingsSection>

      <SettingsSection title="Sessions">
        <SettingsRow
          icon="time-outline"
          title="Session History"
          onPress={() => router.navigate('/history')}
          last
        />
      </SettingsSection>

      <SettingsSection title="About">
        <SettingsRow icon="help-circle-outline" title="Contact Support" comingSoon />
        <SettingsRow icon="document-text-outline" title="Terms and Conditions" comingSoon />
        <SettingsRow icon="shield-checkmark-outline" title="Privacy Policy" comingSoon />
        <SettingsRow icon="information-circle-outline" title="Version" value={appVersionText()} last />
      </SettingsSection>

      <ThemedText type="small" themeColor="textSecondary" style={styles.note}>
        Heads up: replying STOP to our texts turns off all messages from Androyit, including your
        login codes. Reply START to turn them back on.
      </ThemedText>

      <SettingsSection title="Account actions">
        <SettingsRow
          icon="trash-outline"
          title="Delete my account"
          subtitle={
            'Permanently deletes your name, Circle and history.' +
            (checkIn ? ' Your active session will be cancelled.' : '')
          }
          danger
          last
          onPress={() =>
            // Ask twice: this can't be undone.
            confirm('Delete your account?', 'Everything will be permanently deleted.', 'Continue', () =>
              confirm(
                'Are you absolutely sure?',
                'This cannot be undone.',
                'Delete everything',
                handleDelete,
              ),
            )
          }
        />
      </SettingsSection>

      {/* Log out: its own button, centred at the very bottom. */}
      <Pressable
        onPress={() =>
          confirm(
            'Log out?',
            'Your Circle stays saved in your account. Log in again with this number to get it back.',
            'Log out',
            handleLogOut,
          )
        }
        disabled={busy}
        accessibilityRole="button"
        style={({ pressed }) => [
          styles.logOut,
          (pressed || busy) && styles.dimmed,
        ]}>
        <Ionicons name="log-out-outline" size={22} color={Brand.onColor} />
        <ThemedText type="smallBold" style={styles.logOutText}>
          {busy ? 'Please wait…' : 'Log out'}
        </ThemedText>
      </Pressable>
    </Screen>
  );
}

const styles = StyleSheet.create({
  note: {
    marginHorizontal: Spacing.two,
  },
  logOut: {
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.five,
    borderRadius: 999,
    backgroundColor: Brand.red,
    marginTop: Spacing.two,
  },
  logOutText: {
    color: Brand.onColor,
    fontSize: 17,
  },
  dimmed: {
    opacity: 0.6,
  },
});
