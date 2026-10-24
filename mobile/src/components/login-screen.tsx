import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { BigButton } from '@/components/big-button';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSafety } from '@/state/safety-store';
import { formatPhone, formatPhoneInput, isValidPhone, normalizePhone } from '@/utils/phone';

const RESEND_AFTER_SECONDS = 30;

/**
 * Log in with your phone number:
 *   step 1: enter your number -> we text you a 6-digit code
 *   step 2: enter the code -> you're logged in
 * Shown instead of the tabs whenever you're logged out (see _layout.tsx).
 */
export function LoginScreen() {
  const { sendLoginCode, verifyLoginCode } = useSafety();
  const theme = useTheme();

  const [step, setStep] = useState<'phone' | 'code'>('phone');
  const [phone, setPhone] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedPhone = normalizePhone(phone);
  const phoneOk = isValidPhone(normalizedPhone);

  // Countdown before "Send the code again" is allowed.
  const [resendIn, setResendIn] = useState(0);
  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  async function handleSendCode() {
    setBusy(true);
    setError(null);
    const problem = await sendLoginCode(normalizedPhone);
    setBusy(false);
    if (problem) {
      setError(`Couldn't send the code: ${problem}`);
      return;
    }
    setCode('');
    setStep('code');
    setResendIn(RESEND_AFTER_SECONDS);
  }

  async function handleVerify() {
    setBusy(true);
    setError(null);
    const problem = await verifyLoginCode(normalizedPhone, code);
    setBusy(false);
    // On success the app switches to the tabs by itself (the login change is
    // picked up in safety-store.tsx), so there's nothing else to do here.
    if (problem) setError(`That didn't work: ${problem}`);
  }

  const inputStyle = [
    styles.input,
    { color: theme.text, backgroundColor: theme.backgroundElement, borderColor: theme.border },
  ];

  // ----- Step 2: enter the code -----
  if (step === 'code') {
    return (
      <Screen title="Enter your code">
        <ThemedText themeColor="textSecondary">
          We sent a 6-digit code to {formatPhone(normalizedPhone)}.
        </ThemedText>

        <TextInput
          value={code}
          onChangeText={(text) => setCode(text.replace(/\D/g, ''))}
          placeholder="123456"
          placeholderTextColor={theme.textSecondary}
          keyboardType="number-pad"
          maxLength={6}
          // Lets the phone offer to fill in the code from the text message.
          autoComplete="sms-otp"
          textContentType="oneTimeCode"
          autoFocus
          style={[inputStyle, styles.codeInput]}
        />

        {error && (
          <ThemedText type="small" style={{ color: Brand.red }}>
            {error}
          </ThemedText>
        )}

        <BigButton
          label={busy ? 'Checking…' : 'Verify'}
          onPress={handleVerify}
          disabled={code.length !== 6 || busy}
        />
        <BigButton
          label={resendIn > 0 ? `Send the code again (${resendIn}s)` : 'Send the code again'}
          variant="plain"
          onPress={handleSendCode}
          disabled={resendIn > 0 || busy}
        />
        <BigButton
          label="Use a different number"
          variant="plain"
          onPress={() => {
            setStep('phone');
            setError(null);
          }}
        />
      </Screen>
    );
  }

  // ----- Step 1: enter your phone number -----
  return (
    <Screen title="Androyit">
      <ThemedText themeColor="textSecondary">
        Stay safe without giving up your privacy. Log in with your phone number; we&apos;ll text
        you a code.
      </ThemedText>

      <TextInput
        value={phone}
        onChangeText={(text) => setPhone((previous) => formatPhoneInput(text, previous))}
        placeholder="+1 (234) 567-8900"
        placeholderTextColor={theme.textSecondary}
        keyboardType="phone-pad"
        autoComplete="tel"
        style={inputStyle}
      />
      {phone.trim() !== '' && !phoneOk && (
        <ThemedText type="small" style={{ color: Brand.red }}>
          Enter a 10-digit US number, or + and the country code for other countries (e.g. +44 UK, +91 India).
        </ThemedText>
      )}

      {/* Consent: required before sending automated texts to someone. */}
      <Pressable
        onPress={() => setAgreed((a) => !a)}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: agreed }}
        style={styles.consentRow}>
        <View
          style={[
            styles.checkbox,
            { borderColor: agreed ? Brand.green : theme.textSecondary },
            agreed && { backgroundColor: Brand.green },
          ]}>
          {agreed && <ThemedText style={styles.checkmark}>✓</ThemedText>}
        </View>
        <ThemedText type="small" themeColor="textSecondary" style={styles.consentText}>
          I agree to receive automated text messages from Androyit at this number: login codes
          and check-in and safety alerts. Message and data rates may apply. Reply STOP to opt
          out or HELP for help.
        </ThemedText>
      </Pressable>

      {error && (
        <ThemedText type="small" style={{ color: Brand.red }}>
          {error}
        </ThemedText>
      )}

      <BigButton
        label={busy ? 'Sending…' : 'Send code'}
        onPress={handleSendCode}
        disabled={!phoneOk || !agreed || busy}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  input: {
    fontSize: 16,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    borderRadius: 14,
    borderWidth: 1,
  },
  codeInput: {
    fontSize: 28,
    letterSpacing: 8,
    textAlign: 'center',
  },
  consentRow: {
    flexDirection: 'row',
    gap: Spacing.three,
    alignItems: 'flex-start',
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  checkmark: {
    color: Brand.onColor,
    fontSize: 16,
    lineHeight: 20,
  },
  consentText: {
    flex: 1,
  },
});
