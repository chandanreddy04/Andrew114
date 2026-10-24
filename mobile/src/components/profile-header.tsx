import Ionicons from '@expo/vector-icons/Ionicons';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { BigButton } from '@/components/big-button';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSafety } from '@/state/safety-store';

const AVATAR = 112;

// "+15551234567" -> "(555) 123-4567"; other countries stay as they are.
function formatPhone(phone: string) {
  const us = /^\+1(\d{3})(\d{3})(\d{4})$/.exec(phone);
  return us ? `(${us[1]}) ${us[2]}-${us[3]}` : phone;
}

/**
 * The top of Settings: your picture, name and phone number. Tap it to change
 * your name, which your Circle sees in alerts ("Alex hasn't checked in").
 */
export function ProfileHeader() {
  const { profileName, setProfileName, loggedInPhone } = useSafety();
  const theme = useTheme();

  // null = not editing; a string = what's being typed.
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const canSave = draft !== null && draft.trim() !== '' && draft.trim() !== profileName;

  async function save() {
    if (draft === null) return;
    setSaving(true);
    const saved = await setProfileName(draft);
    setSaving(false);
    if (!saved) {
      Alert.alert("Couldn't save", 'The server could not be reached. Check your internet and try again.');
      return;
    }
    setDraft(null);
  }

  return (
    <View style={styles.header}>
      <Pressable
        onPress={() => setDraft(profileName)}
        disabled={draft !== null}
        accessibilityRole="button"
        accessibilityLabel={profileName ? `Edit your name, ${profileName}` : 'Add your name'}
        style={styles.avatarWrap}>
        <View style={[styles.avatar, { backgroundColor: Brand.green }]}>
          <Ionicons name="person" size={AVATAR * 0.55} color={Brand.onColor} />
        </View>
        <View style={[styles.badge, { borderColor: theme.background }]}>
          <Ionicons name="pencil" size={14} color={Brand.onColor} />
        </View>
      </Pressable>

      {draft === null ? (
        <Pressable onPress={() => setDraft(profileName)} accessibilityRole="button" hitSlop={Spacing.two}>
          <ThemedText type="subtitle" style={[styles.name, !profileName && { color: Brand.green }]}>
            {profileName || 'Add your name'}
          </ThemedText>
        </Pressable>
      ) : (
        <View style={styles.editor}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Your first name"
            placeholderTextColor={theme.textSecondary}
            autoCapitalize="words"
            autoFocus
            maxLength={60}
            returnKeyType="done"
            onSubmitEditing={() => canSave && save()}
            style={[
              styles.input,
              { color: theme.text, backgroundColor: theme.backgroundElement, borderColor: theme.border },
            ]}
          />
          <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
            Used in the texts your Circle gets, e.g. &quot;{draft.trim() || 'Alex'} hasn&apos;t
            checked in.&quot;
          </ThemedText>
          <View style={styles.buttons}>
            <View style={styles.flex}>
              <BigButton label="Cancel" variant="plain" size="small" onPress={() => setDraft(null)} />
            </View>
            <View style={styles.flex}>
              <BigButton
                label={saving ? 'Saving…' : 'Save'}
                size="small"
                onPress={save}
                disabled={!canSave || saving}
              />
            </View>
          </View>
        </View>
      )}

      {loggedInPhone && (
        <ThemedText themeColor="textSecondary" style={styles.phone}>
          {formatPhone(loggedInPhone)}
        </ThemedText>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    alignItems: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.two,
  },
  avatarWrap: {
    width: AVATAR,
    height: AVATAR,
  },
  avatar: {
    width: AVATAR,
    height: AVATAR,
    borderRadius: AVATAR / 2,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  badge: {
    position: 'absolute',
    right: 0,
    bottom: 0,
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 3,
    backgroundColor: Brand.green,
    alignItems: 'center',
    justifyContent: 'center',
  },
  name: {
    fontWeight: 800,
    textAlign: 'center',
  },
  phone: {
    fontSize: 18,
  },
  editor: {
    alignSelf: 'stretch',
    gap: Spacing.two,
  },
  input: {
    fontSize: 20,
    textAlign: 'center',
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    borderRadius: 14,
    borderWidth: 1,
  },
  center: {
    textAlign: 'center',
  },
  buttons: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  flex: {
    flex: 1,
  },
});
