import {
  GoogleSansFlex_400Regular,
  GoogleSansFlex_500Medium,
  GoogleSansFlex_600SemiBold,
  GoogleSansFlex_700Bold,
  GoogleSansFlex_800ExtraBold,
} from '@expo-google-fonts/google-sans-flex';
import { type ComponentProps } from 'react';
import {
  StyleSheet,
  Text as RNText,
  TextInput as RNTextInput,
  type TextProps,
  type TextStyle,
} from 'react-native';

/** The font files, loaded once at startup (see app/_layout.tsx). */
export const appFonts = {
  GoogleSansFlex_400Regular,
  GoogleSansFlex_500Medium,
  GoogleSansFlex_600SemiBold,
  GoogleSansFlex_700Bold,
  GoogleSansFlex_800ExtraBold,
};

// Each weight is its own font file, so the weight picks the file. Android
// can't make a loaded font bolder on its own.
function familyFor(weight: TextStyle['fontWeight']) {
  const value = weight === 'bold' ? 700 : Number(weight ?? 400) || 400;
  if (value >= 800) return 'GoogleSansFlex_800ExtraBold';
  if (value >= 700) return 'GoogleSansFlex_700Bold';
  if (value >= 600) return 'GoogleSansFlex_600SemiBold';
  if (value >= 500) return 'GoogleSansFlex_500Medium';
  return 'GoogleSansFlex_400Regular';
}

// Google Sans Flex for any text that doesn't name its own font (e.g. monospace).
function withAppFont(style: TextProps['style']) {
  const flat = StyleSheet.flatten(style) ?? {};
  if (flat.fontFamily) return style;
  return [style, { fontFamily: familyFor(flat.fontWeight), fontWeight: 'normal' as const }];
}

/** React Native's Text, in the app font (Google Sans Flex). */
export function Text({ style, ...rest }: ComponentProps<typeof RNText>) {
  return <RNText style={withAppFont(style)} {...rest} />;
}

/** React Native's TextInput, in the app font (Google Sans Flex). */
export function TextInput({ style, ...rest }: ComponentProps<typeof RNTextInput>) {
  return <RNTextInput style={withAppFont(style)} {...rest} />;
}
