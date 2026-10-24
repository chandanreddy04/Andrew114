import { useSyncExternalStore } from 'react';
import { useColorScheme as useRNColorScheme } from 'react-native';

// Nothing to subscribe to: we only need to know whether we're in the browser yet.
const subscribe = () => () => {};

/**
 * To support static rendering, this value needs to be re-calculated on the client side for web.
 * While the page is pre-rendered (no browser yet) it's always 'light'; once running in the
 * browser it follows the device setting. useSyncExternalStore handles the switch without an
 * extra effect.
 */
export function useColorScheme() {
  const inBrowser = useSyncExternalStore(
    subscribe,
    () => true, // in the browser
    () => false, // while pre-rendering
  );
  const colorScheme = useRNColorScheme();
  return inBrowser ? colorScheme : 'light';
}
