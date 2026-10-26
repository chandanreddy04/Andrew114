import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';

/**
 * "View photo": the photo full screen on black, with Change photo and Remove
 * photo underneath. Used for the profile picture and the outfit photo.
 */
export function PhotoViewer({
  uri,
  visible,
  onClose,
  onChange,
  onRemove,
}: {
  uri: string | null;
  visible: boolean;
  onClose: () => void;
  onChange: () => void;
  onRemove: () => void;
}) {
  const insets = useSafeAreaInsets();

  return (
    <Modal
      visible={visible && !!uri}
      animationType="fade"
      onRequestClose={onClose}
      statusBarTranslucent>
      <View
        style={[
          styles.viewer,
          { paddingTop: insets.top, paddingBottom: insets.bottom + Spacing.four },
        ]}>
        <Pressable
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close photo"
          hitSlop={Spacing.three}
          style={styles.close}>
          <Ionicons name="close" size={30} color="#FFFFFF" />
        </Pressable>
        {uri && <Image source={{ uri }} style={styles.photo} contentFit="contain" />}
        <View style={styles.actions}>
          <Pressable
            onPress={() => {
              onClose();
              onChange();
            }}
            accessibilityRole="button"
            style={styles.button}>
            <Ionicons name="camera-outline" size={20} color="#FFFFFF" />
            <ThemedText style={styles.buttonText}>Change photo</ThemedText>
          </Pressable>
          <Pressable
            onPress={() => {
              onClose();
              onRemove();
            }}
            accessibilityRole="button"
            style={styles.button}>
            <Ionicons name="trash-outline" size={20} color="#FF8A8A" />
            <ThemedText style={[styles.buttonText, { color: '#FF8A8A' }]}>Remove photo</ThemedText>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  viewer: {
    flex: 1,
    backgroundColor: '#000000',
  },
  close: {
    alignSelf: 'flex-end',
    padding: Spacing.three,
  },
  photo: {
    flex: 1,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    paddingTop: Spacing.three,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
  },
});
