import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Platform, StyleSheet } from 'react-native';

import { appVersionText } from '@/components/app-version';
import { Screen } from '@/components/screen';
import { SettingsRow, SettingsSection } from '@/components/settings-list';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useSafety } from '@/state/safety-store';

/**
 * Settings: your account, subscription (coming soon), session history, the
 * "About" links, log out and delete account.
 */
export default function SettingsScreen() {
  const { loggedInPhone, profileName, logOut, deleteAccount, checkIn } = useSafety();
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
    <Screen title="Settings">
      <SettingsSection title="Account">
        <SettingsRow icon="call-outline" title="Phone number" value={loggedInPhone ?? ''} />
        <SettingsRow
          icon="person-outline"
          title="Your name"
          subtitle={profileName || 'Add your name so your Circle knows who it is'}
          onPress={() => router.navigate('/circle')}
          last
        />
      </SettingsSection>

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
          icon="log-out-outline"
          title={busy ? 'Please wait…' : 'Log out'}
          onPress={() =>
            confirm(
              'Log out?',
              'Your Circle stays saved in your account. Log in again with this number to get it back.',
              'Log out',
              handleLogOut,
            )
          }
        />
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
    </Screen>
  );
}

const styles = StyleSheet.create({
  note: {
    marginHorizontal: Spacing.two,
  },
});
