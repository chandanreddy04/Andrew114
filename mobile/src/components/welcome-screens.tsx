import Ionicons from '@expo/vector-icons/Ionicons';
import { type ComponentProps, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BigButton } from '@/components/big-button';
import { ThemedText } from '@/components/themed-text';
import { Brand, BrandGradient, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type Page = {
  icon: ComponentProps<typeof Ionicons>['name'];
  title: string;
  text?: string;
  steps?: string[];
  note?: string;
};

// The three welcome pages. Edit the wording here.
const PAGES: Page[] = [
  {
    icon: 'location',
    title: 'Welcome to Reached',
    text: 'Personal safety for when you go out, without giving up your privacy.',
  },
  {
    icon: 'bulb-outline',
    title: 'How It Works',
    steps: [
      'Set a check-in time',
      'If you miss your check-in, your Circle gets a text',
      "That's it: no tracking, no social feed, no surveillance",
    ],
  },
  {
    icon: 'people',
    title: 'Your Circle has your back',
    steps: [
      "Add the people you trust. They don't need the app",
      'Feel unsafe? SOS sends your location in one tap',
    ],
    note: 'Your location is only shared when you press SOS.',
  },
];

/**
 * A short introduction shown once per phone, before the login screen (see
 * src/app/_layout.tsx). `onDone` is called after "Get started" or "Skip".
 */
export function WelcomeScreens({ onDone }: { onDone: () => void }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [index, setIndex] = useState(0);
  const page = PAGES[index];
  const isLast = index === PAGES.length - 1;

  return (
    <View
      style={[
        styles.screen,
        {
          backgroundColor: theme.background,
          paddingTop: insets.top + Spacing.five,
          paddingBottom: insets.bottom + Spacing.four,
        },
      ]}>
      <View style={styles.page}>
        <View style={styles.iconCircle}>
          <Ionicons name={page.icon} size={56} color={Brand.onColor} />
        </View>

        <ThemedText type="subtitle" style={styles.title}>
          {page.title}
        </ThemedText>

        {page.text && (
          <ThemedText themeColor="textSecondary" style={styles.text}>
            {page.text}
          </ThemedText>
        )}

        {/* Numbered steps, each in a soft teal circle */}
        {page.steps && (
          <View style={styles.steps}>
            {page.steps.map((step, i) => (
              <View key={step} style={styles.stepRow}>
                <View style={[styles.stepNumber, { backgroundColor: theme.backgroundSelected }]}>
                  <Text style={styles.stepNumberText}>{i + 1}</Text>
                </View>
                <ThemedText style={styles.stepText}>{step}</ThemedText>
              </View>
            ))}
          </View>
        )}

        {page.note && (
          <ThemedText type="small" style={[styles.text, { color: Brand.green }]}>
            {page.note}
          </ThemedText>
        )}
      </View>

      {/* Page indicator: the current page is a stretched pill */}
      <View style={styles.dots} accessibilityLabel={`Page ${index + 1} of ${PAGES.length}`}>
        {PAGES.map((p, i) => (
          <View
            key={p.title}
            style={[
              styles.dot,
              i === index
                ? styles.dotActive
                : { backgroundColor: theme.backgroundSelected },
            ]}
          />
        ))}
      </View>

      <View style={styles.buttons}>
        <View style={styles.nextButton}>
          <BigButton
            label={isLast ? 'Get started' : 'Next'}
            trailing="→"
            onPress={isLast ? onDone : () => setIndex(index + 1)}
          />
        </View>
        {isLast ? (
          index > 0 && (
            <Pressable onPress={() => setIndex(index - 1)} accessibilityRole="button" hitSlop={Spacing.three}>
              <Text style={styles.link}>Back</Text>
            </Pressable>
          )
        ) : (
          <Pressable onPress={onDone} accessibilityRole="button" hitSlop={Spacing.three}>
            <Text style={styles.link}>Skip</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const ICON_SIZE = 132;

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    paddingHorizontal: Spacing.four,
    alignItems: 'center',
  },
  page: {
    flex: 1,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.four,
  },
  iconCircle: {
    width: ICON_SIZE,
    height: ICON_SIZE,
    borderRadius: ICON_SIZE / 2,
    backgroundColor: Brand.green,
    experimental_backgroundImage: BrandGradient,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontWeight: 800,
    textAlign: 'center',
  },
  text: {
    textAlign: 'center',
  },
  steps: {
    alignSelf: 'stretch',
    gap: Spacing.four,
    marginTop: Spacing.two,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
  },
  stepNumber: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumberText: {
    color: Brand.green,
    fontSize: 18,
    fontWeight: 700,
  },
  stepText: {
    flex: 1,
    fontSize: 17,
  },
  dots: {
    flexDirection: 'row',
    gap: Spacing.two,
    marginVertical: Spacing.four,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  dotActive: {
    width: 36,
    backgroundColor: Brand.green,
  },
  buttons: {
    alignItems: 'center',
    gap: Spacing.three,
  },
  nextButton: {
    minWidth: 210,
  },
  link: {
    color: Brand.green,
    fontSize: 16,
    fontWeight: 700,
  },
});
