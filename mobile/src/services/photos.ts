/**
 * The outfit photo for a session: take one with the camera or pick one from
 * your photos. Only the photo you choose is used, and it only reaches the
 * server (and your Circle, if an alert triggers) when you start the session.
 */

import type * as ImagePickerTypes from 'expo-image-picker';

export type PhotoResult =
  | { kind: 'picked'; uri: string }
  | { kind: 'cancelled' }
  | { kind: 'denied' } // refused camera / photos permission
  | { kind: 'error'; message: string };

// Smaller files upload faster and stay under the server's 5 MB limit.
const QUALITY = 0.4;

export async function choosePhoto(source: 'camera' | 'library'): Promise<PhotoResult> {
  try {
    // Loaded here (inside try/catch) so a missing module can never crash the
    // Start Session screen.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const ImagePicker = require('expo-image-picker') as typeof ImagePickerTypes;

    const permission =
      source === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return { kind: 'denied' };

    const options: ImagePickerTypes.ImagePickerOptions = {
      mediaTypes: ['images'],
      quality: QUALITY,
      exif: false, // no hidden GPS or camera details in the file
    };
    const result =
      source === 'camera'
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);
    if (result.canceled || !result.assets?.[0]) return { kind: 'cancelled' };
    return { kind: 'picked', uri: result.assets[0].uri };
  } catch (error) {
    return { kind: 'error', message: error instanceof Error ? error.message : 'Unknown error' };
  }
}
