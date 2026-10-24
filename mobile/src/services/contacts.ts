/**
 * Importing a person from the phone's address book into your Circle.
 *
 * Uses the phone's own contact picker: you choose ONE person, and the app
 * reads only that person's name and phone numbers. It never browses or
 * uploads your address book. (Android still asks for the contacts permission,
 * because reading the chosen person's details goes through it.)
 */

import { Platform } from 'react-native';

import type * as ContactsTypes from 'expo-contacts';

export type PhoneOption = { label: string; number: string };

export type PickResult =
  | { kind: 'picked'; name: string; phones: PhoneOption[] }
  | { kind: 'cancelled' } // closed the picker without choosing
  | { kind: 'denied' } // refused the contacts permission
  | { kind: 'unsupported' } // e.g. the web preview
  | { kind: 'error'; message: string };

export async function pickPhoneContact(): Promise<PickResult> {
  if (Platform.OS === 'web') return { kind: 'unsupported' };
  try {
    // Loaded here (inside try/catch) so a missing contacts module can never
    // crash the Circle screen.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Contacts = require('expo-contacts') as typeof ContactsTypes;

    const permission = await Contacts.requestPermissionsAsync();
    if (!permission.granted) return { kind: 'denied' };

    const contact = await Contacts.Contact.presentPicker();
    if (!contact) return { kind: 'cancelled' };

    const details = await contact.getDetails([
      Contacts.ContactField.FULL_NAME,
      Contacts.ContactField.GIVEN_NAME,
      Contacts.ContactField.PHONES,
    ]);
    const name = (details.fullName || details.givenName || '').trim();
    const phones = (details.phones ?? [])
      .filter((p) => !!p.number)
      .map((p) => ({ label: p.label || 'phone', number: p.number as string }));

    return { kind: 'picked', name, phones };
  } catch (error) {
    return { kind: 'error', message: error instanceof Error ? error.message : 'Unknown error' };
  }
}
