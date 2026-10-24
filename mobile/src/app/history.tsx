import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Pressable, StyleSheet } from 'react-native';

import { RecentActivity } from '@/components/recent-activity';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';

/** Session History (opened from Settings): every session and SOS, newest first. */
export default function HistoryScreen() {
  return (
    <Screen title="Session History">
      <Pressable
        onPress={() => router.navigate('/settings')}
        accessibilityRole="button"
        style={styles.back}
        hitSlop={Spacing.three}>
        <Ionicons name="chevron-back" size={20} color={Brand.green} />
        <ThemedText style={{ color: Brand.green }}>Settings</ThemedText>
      </Pressable>
      <RecentActivity filter="all" />
    </Screen>
  );
}

const styles = StyleSheet.create({
  back: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.one,
    marginTop: -Spacing.three,
  },
});
