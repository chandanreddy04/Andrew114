/**
 * Phone numbers in full international format: + country code + number,
 * e.g. +15551234567 (US), +447700900123 (UK), +919876543210 (India).
 * Needed for texting (Twilio) and for logging in.
 *
 * US numbers are always shown as "+1 (234) 567-8900", and phone boxes format
 * them that way while you type.
 */

// Remove spaces, dashes, dots and brackets: "+1 (555) 123-4567" -> "+15551234567".
export function normalizePhone(input: string) {
  return input.replace(/[\s\-().]/g, '');
}

// True for "+" followed by 8 to 15 digits (not starting with 0).
export function isValidPhone(phone: string) {
  return /^\+[1-9]\d{7,14}$/.test(phone);
}

// For showing: "+12345678900" -> "+1 (234) 567-8900"; other countries stay as they are.
export function formatPhone(phone: string) {
  const us = /^\+1(\d{3})(\d{3})(\d{4})$/.exec(normalizePhone(phone));
  return us ? `+1 (${us[1]}) ${us[2]}-${us[3]}` : phone;
}

/**
 * Formats a phone box while you type (use as onChangeText={(t) =>
 * setPhone((prev) => formatPhoneInput(t, prev))}):
 *   "2345678900" or "+12345678900" -> "+1 (234) 567-8900", step by step.
 * A US number is assumed (US area codes never start with 1, so a leading 1 is
 * the country code). Starting with "+" and another country code, e.g. "+44…",
 * leaves the number as typed.
 */
export function formatPhoneInput(text: string, previous = ''): string {
  let digits = text.replace(/\D/g, '');
  // Backspace over a bracket, space or dash: remove the digit before it too,
  // otherwise the formatting would put the symbol straight back.
  if (text.length < previous.length && digits === previous.replace(/\D/g, '')) {
    digits = digits.slice(0, -1);
  }
  if (digits === '') return text.trim().startsWith('+') ? '+' : '';

  // Another country: keep it as "+<digits>".
  if (text.trim().startsWith('+') && !digits.startsWith('1')) return `+${digits.slice(0, 15)}`;

  // US: drop the country code, then format the 10-digit number.
  const national = (digits.startsWith('1') ? digits.slice(1) : digits).slice(0, 10);
  const [area, exchange, line] = [national.slice(0, 3), national.slice(3, 6), national.slice(6)];
  if (national.length === 0) return '+1';
  if (national.length <= 3) return `+1 (${area}`;
  if (national.length <= 6) return `+1 (${area}) ${exchange}`;
  return `+1 (${area}) ${exchange}-${line}`;
}
