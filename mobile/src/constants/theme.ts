/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#2C3E50', // dark navy headings and body text
    background: '#F5F7FA', // light grey page background
    backgroundElement: '#FFFFFF', // white cards
    backgroundSelected: '#E3F5F1', // soft teal (selected items, step circles)
    textSecondary: '#7B8794', // soft grey secondary text
    border: '#D7EEE8', // thin teal-tinted card borders
  },
  dark: {
    text: '#F2F5F7',
    background: '#0F1418',
    backgroundElement: '#1A2228',
    backgroundSelected: '#173A34',
    textSecondary: '#9AA5AF',
    border: '#24333A',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

// The app's brand colours. These look fine in both light and dark mode.
export const Brand = {
  green: '#14A38B', // main teal action colour (buttons, accents, "I'm safe")
  greenDark: '#0F8A76', // darker end of the teal gradient
  red: '#E5484D', // danger / missed check-ins
  yellow: '#FFD43B', // the SOS button
  onColor: '#ffffff', // text drawn on top of teal or red
  onYellow: '#3A2F00', // text drawn on top of yellow
} as const;

// Soft teal gradient for main buttons and icon circles (plain styling, so it
// works without any extra library).
export const BrandGradient = `linear-gradient(135deg, #1BB99F, ${Brand.greenDark})`;

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

// Extra space at the bottom of each screen so content clears the raised SOS
// button, which sticks up above the tab bar.
export const BottomTabInset = 28;
export const MaxContentWidth = 800;
