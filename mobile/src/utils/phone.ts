/**
 * Phone numbers in full international format: + country code + number,
 * e.g. +15551234567 (US), +447700900123 (UK), +919876543210 (India).
 * Needed for texting (Twilio) and for logging in.
 */

// Remove spaces, dashes, dots and brackets: "+1 (555) 123-4567" -> "+15551234567".
export function normalizePhone(input: string) {
  return input.replace(/[\s\-().]/g, '');
}

// True for "+" followed by 8 to 15 digits (not starting with 0).
export function isValidPhone(phone: string) {
  return /^\+[1-9]\d{7,14}$/.test(phone);
}
