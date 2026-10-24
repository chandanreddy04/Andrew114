import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';

import { BigButton } from '@/components/big-button';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { choosePhoto } from '@/services/photos';
import { useSafety } from '@/state/safety-store';
import { formatPhone } from '@/utils/phone';

const AVATAR = 150;

/**
 * Edit Profile (opened from the top of Settings): your photo and name. Your
 * Circle sees both in alerts. Nothing changes until you tap Save Changes.
 */
export default function EditProfileScreen() {
  const { profileName, setProfileName, profilePhotoUri, setProfilePhoto, loggedInPhone } =
    useSafety();
  const theme = useTheme();

  const [name, setName] = useState(profileName);
  // undefined = photo unchanged; a file = new photo; null = remove it.
  const [newPhoto, setNewPhoto] = useState<string | null | undefined>(undefined);
  const [saving, setSaving] = useState(false);

  // This screen stays loaded in the background, so start fresh each time it opens.
  useFocusEffect(
    useCallback(() => {
      setName(profileName);
      setNewPhoto(undefined);
    }, [profileName]),
  );

  const shownPhoto = newPhoto !== undefined ? newPhoto : profilePhotoUri;
  const nameChanged = name.trim() !== profileName;
  const changed = nameChanged || newPhoto !== undefined;
  const canSave = changed && name.trim() !== '' && !saving;

  function close() {
    router.navigate('/settings');
  }

  async function pick(source: 'camera' | 'library') {
    const result = await choosePhoto(source, { square: true });
    if (result.kind === 'picked') setNewPhoto(result.uri);
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
      ...(shownPhoto
        ? [{ text: 'Remove photo', style: 'destructive' as const, onPress: () => setNewPhoto(null) }]
        : []),
      { text: 'Cancel', style: 'cancel' as const },
    ]);
  }

  async function save() {
    setSaving(true);
    const problems: string[] = [];
    if (nameChanged && !(await setProfileName(name))) {
      problems.push("Your name couldn't be saved.");
    }
    if (newPhoto !== undefined) {
      const problem = await setProfilePhoto(newPhoto);
      if (problem) problems.push(`Your photo couldn't be saved (${problem}).`);
    }
    setSaving(false);
    if (problems.length > 0) {
      Alert.alert("Couldn't save everything", `${problems.join('\n')}\n\nCheck your internet and try again.`);
      return;
    }
    close();
  }

  const field = { backgroundColor: theme.backgroundElement, color: theme.text };

  return (
    <Screen title="">
      {/* Header: back, and the title in the middle. */}
      <View style={styles.header}>
        <Pressable
          onPress={close}
          accessibilityRole="button"
          accessibilityLabel="Back to Settings"
          hitSlop={Spacing.two}
          style={[styles.back, { backgroundColor: theme.backgroundElement, borderColor: theme.border }]}>
          <Ionicons name="chevron-back" size={24} color={Brand.green} />
        </Pressable>
        <ThemedText type="smallBold" style={styles.title}>
          Edit Profile
        </ThemedText>
        <View style={styles.backSpace} />
      </View>

      {/* Photo */}
      <View style={styles.photoSection}>
        <Pressable
          onPress={handlePhotoPress}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel={shownPhoto ? 'Change your profile photo' : 'Add a profile photo'}
          style={styles.avatarWrap}>
          <View style={[styles.avatar, { backgroundColor: theme.backgroundSelected }]}>
            {shownPhoto ? (
              <Image source={{ uri: shownPhoto }} style={styles.photo} contentFit="cover" />
            ) : (
              <Ionicons name="person" size={AVATAR * 0.45} color={theme.textSecondary} />
            )}
          </View>
          <View style={[styles.badge, { borderColor: theme.background }]}>
            <Ionicons name="camera" size={20} color={Brand.onColor} />
          </View>
        </Pressable>
        <ThemedText themeColor="textSecondary">Tap to change photo</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          Your photo will be visible to your Circle of Trust
        </ThemedText>
      </View>

      {/* Full name */}
      <View style={styles.fieldGroup}>
        <ThemedText type="smallBold" style={styles.label}>
          Full Name
        </ThemedText>
        <TextInput
          value={name}
          onChangeText={setName}
          placeholder="Your name"
          placeholderTextColor={theme.textSecondary}
          autoCapitalize="words"
          maxLength={60}
          returnKeyType="done"
          style={[styles.input, field]}
        />
        <ThemedText type="small" themeColor="textSecondary">
          Used in the texts your Circle gets, e.g. &quot;{name.trim() || 'Alex'} hasn&apos;t checked
          in.&quot;
        </ThemedText>
      </View>

      {/* Phone number: it's your login, so it can't be edited here. */}
      <View style={styles.fieldGroup}>
        <ThemedText type="smallBold" style={styles.label}>
          Phone Number
        </ThemedText>
        <View style={[styles.input, styles.locked, { backgroundColor: theme.backgroundSelected }]}>
          <ThemedText themeColor="textSecondary" style={styles.lockedText}>
            {loggedInPhone ? formatPhone(loggedInPhone) : ''}
          </ThemedText>
          <Ionicons name="lock-closed" size={18} color={theme.textSecondary} />
        </View>
        <ThemedText type="small" themeColor="textSecondary">
          Log in with a different number to change
        </ThemedText>
      </View>

      <View style={styles.buttons}>
        {saving ? (
          <ActivityIndicator color={Brand.green} />
        ) : (
          <BigButton label="Save Changes" onPress={save} disabled={!canSave} />
        )}
        <BigButton label="Cancel" variant="plain" onPress={close} disabled={saving} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  back: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backSpace: {
    width: 48,
  },
  title: {
    fontSize: 20,
    lineHeight: 26,
    color: Brand.green,
  },
  photoSection: {
    alignItems: 'center',
    gap: Spacing.one,
    paddingVertical: Spacing.two,
  },
  avatarWrap: {
    width: AVATAR,
    height: AVATAR,
    marginBottom: Spacing.two,
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
  badge: {
    position: 'absolute',
    right: 2,
    bottom: 2,
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 3,
    backgroundColor: Brand.green,
    alignItems: 'center',
    justifyContent: 'center',
  },
  center: {
    textAlign: 'center',
  },
  fieldGroup: {
    gap: Spacing.two,
  },
  label: {
    fontSize: 17,
  },
  input: {
    fontSize: 18,
    minHeight: 54,
    paddingHorizontal: Spacing.three,
    borderRadius: 14,
    justifyContent: 'center',
  },
  locked: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  lockedText: {
    flex: 1,
    fontSize: 18,
  },
  buttons: {
    gap: Spacing.three,
    marginTop: Spacing.two,
  },
});
