import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSafety } from '@/state/safety-store';
import { formatPhone } from '@/utils/phone';

const AVATAR = 112;

/**
 * The top of Settings: your picture, name and phone number. Tap it (or the
 * pencil) to open Edit Profile.
 */
export function ProfileHeader() {
  const { profileName, loggedInPhone, profilePhotoUri } = useSafety();
  const theme = useTheme();

  return (
    <Pressable
      onPress={() => router.navigate('/edit-profile')}
      accessibilityRole="button"
      accessibilityLabel="Edit profile"
      style={styles.header}>
      <View style={styles.avatarWrap}>
        <View style={[styles.avatar, { backgroundColor: Brand.green }]}>
          {profilePhotoUri ? (
            <Image source={{ uri: profilePhotoUri }} style={styles.photo} contentFit="cover" />
          ) : (
            <Ionicons name="person" size={AVATAR * 0.55} color={Brand.onColor} />
          )}
        </View>
        <View style={[styles.badge, { borderColor: theme.background }]}>
          <Ionicons name="pencil" size={15} color={Brand.onColor} />
        </View>
      </View>

      <ThemedText type="subtitle" style={[styles.name, !profileName && { color: Brand.green }]}>
        {profileName || 'Add your name'}
      </ThemedText>
      {loggedInPhone && (
        <ThemedText themeColor="textSecondary" style={styles.phone}>
          {formatPhone(loggedInPhone)}
        </ThemedText>
      )}
    </Pressable>
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
  photo: {
    width: '100%',
    height: '100%',
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
});
