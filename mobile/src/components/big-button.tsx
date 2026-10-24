import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Brand, brandGradientStyle, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type BigButtonProps = {
  label: string;
  onPress: () => void;
  // "primary" = teal gradient, "danger" = red, "plain" = white card,
  // "outline" = teal outline (e.g. the -30m / +30m pills)
  variant?: 'primary' | 'danger' | 'plain' | 'outline';
  // "medium" a bit smaller than normal (forms); "small" for compact pills
  size?: 'normal' | 'medium' | 'small';
  // Text after the label, e.g. "→" on "Next →"
  trailing?: string;
  disabled?: boolean;
};

/** A large, easy-to-tap pill-shaped button used across the app. */
export function BigButton({
  label,
  onPress,
  variant = 'primary',
  size = 'normal',
  trailing,
  disabled,
}: BigButtonProps) {
  const theme = useTheme();

  const look = {
    primary: { ...brandGradientStyle, backgroundColor: Brand.green },
    danger: { backgroundColor: Brand.red },
    plain: { backgroundColor: theme.backgroundElement, borderWidth: 1, borderColor: theme.border },
    outline: { backgroundColor: 'transparent', borderWidth: 1.5, borderColor: Brand.green },
  }[variant];
  const textColor =
    variant === 'plain' ? theme.text : variant === 'outline' ? Brand.green : Brand.onColor;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      // `pressed` is true while your finger is on the button, so it dims slightly.
      style={({ pressed }) => [
        styles.button,
        size === 'medium' && styles.medium,
        size === 'small' && styles.small,
        look,
        (pressed || disabled) && styles.dimmed,
      ]}>
      <View style={styles.row}>
        <Text
          style={[
            styles.label,
            size === 'medium' && styles.mediumLabel,
            size === 'small' && styles.smallLabel,
            { color: textColor },
          ]}>
          {label}
        </Text>
        {trailing && <Text style={[styles.label, { color: textColor }]}>{trailing}</Text>}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingVertical: Spacing.three + 2,
    paddingHorizontal: Spacing.four,
    borderRadius: 999,
    alignItems: 'center',
  },
  medium: {
    paddingVertical: Spacing.two + 4,
  },
  small: {
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.four,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  label: {
    fontSize: 17,
    fontWeight: 700,
  },
  mediumLabel: {
    fontSize: 16,
  },
  smallLabel: {
    fontSize: 15,
    fontWeight: 600,
  },
  dimmed: {
    opacity: 0.5,
  },
});
