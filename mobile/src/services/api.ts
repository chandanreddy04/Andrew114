/**
 * The low-level connection to the Reached API (our own FastAPI backend,
 * see backend/ in this repo). Everything is plain HTTP + JSON.
 *
 * Login tokens:
 * - The access token goes with every request ("Authorization: Bearer …").
 * - When it expires, the refresh token is swapped for a new pair, once, and
 *   the request is retried. If that fails too, you're logged out.
 * Both are kept in the phone's secure storage (Android Keystore), not in
 * plain app storage.
 */

import { Platform } from 'react-native';

import type * as SecureStoreTypes from 'expo-secure-store';

// From .env.local or the EAS environment (EXPO_PUBLIC_ values are built into
// the app). On the Android emulator, http://10.0.2.2:8000 is your computer.
export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? '').replace(/\/+$/, '');

if (!API_URL) {
  console.warn('EXPO_PUBLIC_API_URL is missing: check .env.local. Running without a server.');
}

// Long enough for a photo upload on a slow connection.
const REQUEST_TIMEOUT_MS = 45 * 1000;

// ----- Where the tokens are kept -----

const ACCESS_KEY = 'reached.access-token';
const REFRESH_KEY = 'reached.refresh-token';
const PHONE_KEY = 'reached.phone';

// The web preview has no secure storage; it keeps tokens in localStorage.
function loadSecureStore(): typeof SecureStoreTypes | null {
  if (Platform.OS === 'web') return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('expo-secure-store') as typeof SecureStoreTypes;
  } catch {
    return null;
  }
}
const SecureStore = loadSecureStore();

const storage = {
  async get(key: string): Promise<string | null> {
    if (SecureStore) return SecureStore.getItemAsync(key);
    if (typeof localStorage !== 'undefined') return localStorage.getItem(key);
    return null;
  },
  async set(key: string, value: string) {
    if (SecureStore) return SecureStore.setItemAsync(key, value);
    if (typeof localStorage !== 'undefined') localStorage.setItem(key, value);
  },
  async remove(key: string) {
    if (SecureStore) return SecureStore.deleteItemAsync(key);
    if (typeof localStorage !== 'undefined') localStorage.removeItem(key);
  },
};

export type Session = { accessToken: string; refreshToken: string; phone: string };

let session: Session | null = null;
let sessionLoaded: Promise<void> | null = null;
const listeners = new Set<() => void>();

function loadSession(): Promise<void> {
  sessionLoaded ??= (async () => {
    try {
      const [accessToken, refreshToken, phone] = await Promise.all([
        storage.get(ACCESS_KEY),
        storage.get(REFRESH_KEY),
        storage.get(PHONE_KEY),
      ]);
      session = accessToken && refreshToken && phone ? { accessToken, refreshToken, phone } : null;
    } catch {
      session = null;
    }
  })();
  return sessionLoaded;
}

export async function getSession(): Promise<Session | null> {
  await loadSession();
  return session;
}

export async function setSession(next: Session | null) {
  await loadSession();
  const changed = (session === null) !== (next === null) || session?.phone !== next?.phone;
  session = next;
  try {
    if (next) {
      await Promise.all([
        storage.set(ACCESS_KEY, next.accessToken),
        storage.set(REFRESH_KEY, next.refreshToken),
        storage.set(PHONE_KEY, next.phone),
      ]);
    } else {
      await Promise.all([storage.remove(ACCESS_KEY), storage.remove(REFRESH_KEY), storage.remove(PHONE_KEY)]);
    }
  } catch (error) {
    console.warn('Could not save login', error);
  }
  if (changed) listeners.forEach((listener) => listener());
}

/** Calls `onChange` whenever you log in or out. Returns a function to stop listening. */
export function onSessionChange(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

// ----- Requests -----

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  // status 0 = couldn't reach the server at all (no internet, server down).
  | { ok: false; status: number; error: string };

type TokensResponse = {
  access_token: string;
  refresh_token: string;
  user: { phone: string };
};

/** Save the tokens from a login or refresh response. */
export async function saveTokens(data: TokensResponse) {
  await setSession({
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    phone: data.user.phone,
  });
}

// Several requests can fail with "expired" at once; refresh only once.
let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  refreshing ??= (async () => {
    const current = await getSession();
    if (!current) return false;
    const result = await send<TokensResponse>('POST', '/v1/auth/refresh', {
      refresh_token: current.refreshToken,
    });
    if (result.ok) {
      await saveTokens(result.data);
      return true;
    }
    // Only a definite "no" logs you out; a network blip doesn't.
    if (result.status === 401) await setSession(null);
    return false;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function send<T>(method: string, path: string, body?: unknown, token?: string): Promise<ApiResult<T>> {
  if (!API_URL) return { ok: false, status: 0, error: 'Not connected to the server' };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  // A FormData body (a photo upload) is sent as-is; fetch sets its own
  // multipart Content-Type. Everything else is JSON.
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  try {
    const response = await fetch(API_URL + path, {
      method,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: isForm ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const text = await response.text();
    const data = text ? safeJson(text) : null;
    if (response.ok) return { ok: true, status: response.status, data: data as T };
    return { ok: false, status: response.status, error: errorMessage(data, response.status) };
  } catch {
    return { ok: false, status: 0, error: 'Could not reach the server. Check your internet.' };
  } finally {
    clearTimeout(timer);
  }
}

/** A request as the logged-in user (refreshes the login if it expired). */
export async function request<T>(method: string, path: string, body?: unknown): Promise<ApiResult<T>> {
  const current = await getSession();
  if (!current) return { ok: false, status: 401, error: 'Not logged in' };

  const first = await send<T>(method, path, body, current.accessToken);
  if (first.ok || first.status !== 401) return first;

  if (!(await refreshTokens())) return first;
  const renewed = await getSession();
  return send<T>(method, path, body, renewed?.accessToken);
}

/** A request without logging in (sending and checking login codes). */
export function publicRequest<T>(method: string, path: string, body?: unknown) {
  return send<T>(method, path, body);
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

// FastAPI errors look like {"detail": "message"} or, for invalid input,
// {"detail": [{"msg": "Value error, Use + and the country code…"}]}.
function errorMessage(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') {
    return detail[0].msg.replace(/^Value error, /, '');
  }
  return `Server error (${status})`;
}
