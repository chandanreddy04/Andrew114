import Ionicons from '@expo/vector-icons/Ionicons';
import { type ComponentProps, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Text } from '@/components/text';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

/** A titled group of rows, like "SUBSCRIPTION" or "ABOUT" in Settings. */
export function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={styles.section}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.sectionTitle}>
        {title.toUpperCase()}
      </ThemedText>
      <View
        style={[styles.group, { backgroundColor: theme.backgroundElement, borderColor: theme.border }]}>
        {children}
      </View>
    </View>
  );
}

type RowProps = {
  icon: ComponentProps<typeof Ionicons>['name'];
  title: string;
  subtitle?: string;
  value?: string; // shown on the right (e.g. the version)
  onPress?: () => void; // shows a › arrow when set
  comingSoon?: boolean; // greyed out with a "Coming soon" label
  danger?: boolean; // red text (e.g. Delete my account)
  last?: boolean; // no divider line below the last row
};

/** One row: icon on the left, title (+ subtitle), and a value or › on the right. */
export function SettingsRow({
  icon,
  title,
  subtitle,
  value,
  onPress,
  comingSoon,
  danger,
  last,
}: RowProps) {
  const theme = useTheme();
  const color = danger ? Brand.red : Brand.green;
  const tappable = !!onPress && !comingSoon;

  return (
    <Pressable
      onPress={tappable ? onPress : undefined}
      disabled={!tappable}
      accessibilityRole={tappable ? 'button' : undefined}
      accessibilityState={{ disabled: comingSoon }}
      style={({ pressed }) => [
        styles.row,
        !last && { borderBottomWidth: 1, borderBottomColor: theme.border },
        pressed && tappable && { backgroundColor: theme.backgroundSelected },
        comingSoon && styles.comingSoon,
      ]}>
      <Ionicons name={icon} size={24} color={color} />
      <View style={styles.texts}>
        <ThemedText style={[styles.title, danger && { color: Brand.red }]}>{title}</ThemedText>
        {(subtitle || comingSoon) && (
          <ThemedText type="small" themeColor="textSecondary">
            {comingSoon ? 'Coming soon' : subtitle}
          </ThemedText>
        )}
      </View>
      {value && (
        <Text style={[styles.value, { color: theme.textSecondary }]} numberOfLines={2}>
          {value}
        </Text>
      )}
      {tappable && <Ionicons name="chevron-forward" size={20} color={theme.textSecondary} />}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: Spacing.two,
  },
  sectionTitle: {
    letterSpacing: 1,
    marginLeft: Spacing.two,
  },
  group: {
    borderRadius: 18,
    borderWidth: 1,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    minHeight: 60,
  },
  comingSoon: {
    opacity: 0.55,
  },
  texts: {
    flex: 1,
  },
  title: {
    fontSize: 17,
  },
  value: {
    maxWidth: '45%',
    textAlign: 'right',
    fontSize: 14,
  },
});
