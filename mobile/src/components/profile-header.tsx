import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { useState } from 'react';
import { ActivityIndicator, Alert, Platform, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { BigButton } from '@/components/big-button';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { choosePhoto } from '@/services/photos';
import { useSafety } from '@/state/safety-store';

const AVATAR = 128;

// "+15551234567" -> "(555) 123-4567"; other countries stay as they are.
function formatPhone(phone: string) {
  const us = /^\+1(\d{3})(\d{3})(\d{4})$/.exec(phone);
  return us ? `(${us[1]}) ${us[2]}-${us[3]}` : phone;
}

/**
 * The top of Settings: your picture, name and phone number.
 * - Tap the picture to take or choose one. Your Circle sees it on alert pages.
 * - Tap your name to change it ("Alex hasn't checked in").
 */
export function ProfileHeader() {
  const { profileName, setProfileName, loggedInPhone, profilePhotoUri, setProfilePhoto } =
    useSafety();
  const theme = useTheme();

  // ----- Profile picture -----
  const [photoBusy, setPhotoBusy] = useState(false);

  async function changePhoto(next: string | null) {
    setPhotoBusy(true);
    const problem = await setProfilePhoto(next);
    setPhotoBusy(false);
    if (problem) Alert.alert("Couldn't save your photo", problem);
  }

  async function pick(source: 'camera' | 'library') {
    const result = await choosePhoto(source, { square: true });
    if (result.kind === 'picked') await changePhoto(result.uri);
    else if (result.kind === 'denied') {
      Alert.alert(
        source === 'camera' ? 'Camera not allowed' : 'Photos not allowed',
        "You can allow it for Androyit in your phone's Settings.",
      );
    } else if (result.kind === 'error') {
      Alert.alert("Couldn't get the photo", result.message);
    }
  }

  function handlePhotoPress() {
    if (Platform.OS === 'web') return pick('library');
    Alert.alert('Profile photo', 'Your photo will be visible to your Circle of Trust.', [
      { text: 'Take photo', onPress: () => pick('camera') },
      { text: 'Choose from photos', onPress: () => pick('library') },
      ...(profilePhotoUri
        ? [{ text: 'Remove photo', style: 'destructive' as const, onPress: () => changePhoto(null) }]
        : []),
      { text: 'Cancel', style: 'cancel' as const },
    ]);
  }

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
        onPress={handlePhotoPress}
        disabled={photoBusy}
        accessibilityRole="button"
        accessibilityLabel={profilePhotoUri ? 'Change your profile photo' : 'Add a profile photo'}
        style={styles.avatarWrap}>
        <View style={[styles.avatar, { backgroundColor: theme.backgroundSelected }]}>
          {profilePhotoUri ? (
            <Image source={{ uri: profilePhotoUri }} style={styles.photo} contentFit="cover" />
          ) : (
            <Ionicons name="person" size={AVATAR * 0.5} color={theme.textSecondary} />
          )}
          {photoBusy && (
            <View style={styles.busy}>
              <ActivityIndicator color={Brand.onColor} />
            </View>
          )}
        </View>
        <View style={[styles.badge, { borderColor: theme.background }]}>
          <Ionicons name="camera" size={18} color={Brand.onColor} />
        </View>
      </Pressable>
      <View style={styles.photoNote}>
        <ThemedText themeColor="textSecondary">
          {profilePhotoUri ? 'Tap to change photo' : 'Tap to add a photo'}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          Your photo will be visible to your Circle of Trust
        </ThemedText>
      </View>

      {draft === null ? (
        <Pressable
          onPress={() => setDraft(profileName)}
          accessibilityRole="button"
          accessibilityLabel={profileName ? `Edit your name, ${profileName}` : 'Add your name'}
          hitSlop={Spacing.two}
          style={styles.nameRow}>
          <ThemedText type="subtitle" style={[styles.name, !profileName && { color: Brand.green }]}>
            {profileName || 'Add your name'}
          </ThemedText>
          <Ionicons name="pencil" size={18} color={Brand.green} />
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
    borderWidth: 4,
    borderColor: Brand.green,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  photo: {
    width: '100%',
    height: '100%',
  },
  busy: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.35)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoNote: {
    alignItems: 'center',
    gap: 2,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    marginTop: Spacing.two,
  },
  badge: {
    position: 'absolute',
    right: 0,
    bottom: 0,
    width: 40,
    height: 40,
    borderRadius: 20,
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
