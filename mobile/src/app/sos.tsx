import { Redirect } from 'expo-router';

/**
 * SOS isn't a page any more: hold the yellow SOS button (on every screen) for
 * 3 seconds, and the SOS card appears on Home. This route only exists because
 * the tab bar's SOS slot needs one; anything that opens it lands on Home.
 */
export default function SosScreen() {
  return <Redirect href="/" />;
}
