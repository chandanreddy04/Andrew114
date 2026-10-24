/**
 * Your profile picture. The server keeps it (so your Circle sees it on alert
 * pages, and it comes back on a new phone); this phone keeps a copy in its
 * own app storage so it shows instantly.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

import { API_URL, getSession, request, uploadFile } from '@/services/api';

const KEY = 'reached:profile-photo';

export type SavedPhoto = { uri: string; updatedAt: string };

type FileSystemModule = typeof import('expo-file-system/legacy');

function fileSystem(): FileSystemModule | null {
  if (Platform.OS === 'web') return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('expo-file-system/legacy') as FileSystemModule;
  } catch {
    return null;
  }
}

export async function loadSavedPhoto(): Promise<SavedPhoto | null> {
  try {
    const text = await AsyncStorage.getItem(KEY);
    return text ? (JSON.parse(text) as SavedPhoto) : null;
  } catch {
    return null;
  }
}

async function remember(photo: SavedPhoto | null) {
  if (photo) await AsyncStorage.setItem(KEY, JSON.stringify(photo)).catch(() => {});
  else await AsyncStorage.removeItem(KEY).catch(() => {});
}

// A new file name each time, so the picture never shows a stale cached copy.
function localPath(fs: FileSystemModule) {
  return `${fs.documentDirectory}profile-${Date.now()}.jpg`;
}

async function deleteLocal(uri: string | undefined) {
  const fs = fileSystem();
  if (fs && uri?.startsWith(fs.documentDirectory ?? '\0')) {
    await fs.deleteAsync(uri, { idempotent: true }).catch(() => {});
  }
}

// The web preview: the picked file is a blob: or data: URL in the browser.
async function uploadFromBrowser(uri: string) {
  const form = new FormData();
  try {
    form.append('photo', await (await fetch(uri)).blob(), 'profile.jpg');
  } catch {
    return { ok: false as const, error: 'Could not read the photo' };
  }
  return request('PUT', '/v1/me/photo', form);
}

/** Upload a newly picked picture. Returns the saved copy, or an error message. */
export async function uploadProfilePhoto(
  pickedUri: string,
): Promise<{ ok: true; photo: SavedPhoto } | { ok: false; error: string }> {
  const result =
    Platform.OS === 'web'
      ? await uploadFromBrowser(pickedUri)
      : await uploadFile('PUT', '/v1/me/photo', pickedUri, 'photo', 'image/jpeg');
  if (!result.ok) return { ok: false, error: result.error };

  // Keep our own copy: the picker's file lives in a cache that can be cleared.
  let uri = pickedUri;
  const fs = fileSystem();
  if (fs?.documentDirectory) {
    const target = localPath(fs);
    try {
      await fs.copyAsync({ from: pickedUri, to: target });
      uri = target;
    } catch {
      // Fine: we show the picked file instead.
    }
  }
  // The server's time for this picture, so other phones can tell it's newer.
  const me = await request<{ photo_updated_at: string | null }>('GET', '/v1/me');
  const updatedAt = (me.ok && me.data.photo_updated_at) || new Date().toISOString();
  const previous = await loadSavedPhoto();
  const photo = { uri, updatedAt };
  await remember(photo);
  if (previous && previous.uri !== uri) await deleteLocal(previous.uri);
  return { ok: true, photo };
}

export async function removeProfilePhoto(): Promise<boolean> {
  const result = await request('DELETE', '/v1/me/photo');
  if (!result.ok) return false;
  const previous = await loadSavedPhoto();
  await remember(null);
  await deleteLocal(previous?.uri);
  return true;
}

/**
 * Match this phone's copy to the server's (e.g. after logging in on a new
 * phone, or changing the picture on another one). serverUpdatedAt is from
 * /v1/me: null means there's no picture.
 */
export async function syncProfilePhoto(serverUpdatedAt: string | null): Promise<SavedPhoto | null> {
  const saved = await loadSavedPhoto();
  if (!serverUpdatedAt) {
    if (saved) {
      await remember(null);
      await deleteLocal(saved.uri);
    }
    return null;
  }
  if (saved && new Date(saved.updatedAt).getTime() >= new Date(serverUpdatedAt).getTime()) {
    return saved;
  }

  const fs = fileSystem();
  const session = await getSession();
  if (!fs?.documentDirectory || !session || !API_URL) return saved;
  try {
    const target = localPath(fs);
    const result = await fs.downloadAsync(API_URL + '/v1/me/photo', target, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });
    if (result.status !== 200) return saved;
    const photo = { uri: target, updatedAt: serverUpdatedAt };
    await remember(photo);
    if (saved) await deleteLocal(saved.uri);
    return photo;
  } catch {
    return saved;
  }
}

/** Forget the phone's copy (after logging out or deleting the account). */
export async function forgetProfilePhoto() {
  const saved = await loadSavedPhoto();
  await remember(null);
  await deleteLocal(saved?.uri);
}
