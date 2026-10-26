import { type AlertButton, Platform } from 'react-native';

/**
 * Dialog buttons in the order they should appear, top to bottom.
 *
 * Android stacks dialog buttons bottom-up (the last one ends up on top), so
 * they're passed reversed there. Android also shows at most 3 buttons; keep
 * menus to 3 (tapping outside a dialog closes it).
 */
export function inShownOrder(buttons: AlertButton[]): AlertButton[] {
  return Platform.OS === 'android' ? [...buttons].reverse() : buttons;
}
