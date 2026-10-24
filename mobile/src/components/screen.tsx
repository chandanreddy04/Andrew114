import { type ReactNode } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

/**
 * The common frame every screen sits in: a title at the top, scrollable
 * content, and padding so nothing hides behind the phone's notch or the tab bar.
 */
export function Screen({ title, children }: { title: string; children: ReactNode }) {
  const insets = useSafeAreaInsets(); // space taken by the notch / status bar
  const theme = useTheme();

  return (
    <ScrollView
      style={{ backgroundColor: theme.background }}
      // Lets you tap buttons while the keyboard is open.
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={[
        styles.content,
        {
          paddingTop: insets.top + Spacing.four,
          paddingBottom: insets.bottom + BottomTabInset + Spacing.four,
        },
      ]}>
      {title !== '' && (
        <ThemedText type="subtitle" style={styles.title}>
          {title}
        </ThemedText>
      )}
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  title: {
    fontWeight: 800,
  },
  content: {
    paddingHorizontal: Spacing.four,
    gap: Spacing.four,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
});
