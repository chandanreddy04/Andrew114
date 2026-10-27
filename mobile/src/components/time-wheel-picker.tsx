import { useRef, useState } from 'react';
import {
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { formatClock } from '@/utils/time';

const ITEM = 44; // height of one row in a wheel
const VISIBLE = 5; // rows shown; the middle one is the choice
const MINUTE_STEP = 5;

const HOURS = Array.from({ length: 12 }, (_, i) => String(i + 1)); // 1 … 12
const MINUTES = Array.from({ length: 60 / MINUTE_STEP }, (_, i) =>
  String(i * MINUTE_STEP).padStart(2, '0'),
); // 00 … 55
const PERIODS = ['AM', 'PM'];

// The next time this clock time comes round: today, or tomorrow if it has passed.
function nextOccurrence(hourIndex: number, minuteIndex: number, periodIndex: number): Date {
  const hour24 = ((hourIndex + 1) % 12) + (periodIndex === 1 ? 12 : 0);
  const date = new Date();
  date.setHours(hour24, minuteIndex * MINUTE_STEP, 0, 0);
  if (date.getTime() <= Date.now()) date.setDate(date.getDate() + 1);
  return date;
}

function isTomorrow(date: Date) {
  return date.toDateString() !== new Date().toDateString();
}

/**
 * "Be back by" time chooser: scroll wheels for hour, minute (5-minute steps) and
 * AM/PM, opened by tapping the time on Start Session. Done is only allowed
 * between `earliest` and `latest` (timestamps).
 */
export function TimeWheelPicker({
  visible,
  value,
  earliest,
  latest,
  onCancel,
  onDone,
}: {
  visible: boolean;
  value: Date;
  earliest: number;
  latest: number;
  onCancel: () => void;
  onDone: (time: Date) => void;
}) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  const hours = value.getHours();
  const [hour, setHour] = useState(((hours % 12) || 12) - 1);
  const [minute, setMinute] = useState(Math.round(value.getMinutes() / MINUTE_STEP) % MINUTES.length);
  const [period, setPeriod] = useState(hours >= 12 ? 1 : 0);

  const chosen = nextOccurrence(hour, minute, period);
  const tooSoon = chosen.getTime() < earliest;
  const tooLate = chosen.getTime() > latest;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <Pressable style={styles.backdrop} onPress={onCancel} accessibilityLabel="Close" />
      <View
        style={[
          styles.sheet,
          { backgroundColor: theme.backgroundElement, paddingBottom: insets.bottom + Spacing.four },
        ]}>
        <View style={styles.header}>
          <Pressable onPress={onCancel} accessibilityRole="button" hitSlop={Spacing.two}>
            <ThemedText themeColor="textSecondary">Cancel</ThemedText>
          </Pressable>
          <ThemedText type="smallBold" style={styles.title}>
            Be back by
          </ThemedText>
          <Pressable
            onPress={() => onDone(chosen)}
            disabled={tooSoon || tooLate}
            accessibilityRole="button"
            hitSlop={Spacing.two}>
            <ThemedText
              type="smallBold"
              style={{ color: tooSoon || tooLate ? theme.textSecondary : Brand.green }}>
              Done
            </ThemedText>
          </Pressable>
        </View>

        <View style={styles.wheels}>
          {/* The band behind the middle row marks the choice. */}
          <View
            pointerEvents="none"
            style={[styles.band, { backgroundColor: theme.backgroundSelected }]}
          />
          <Wheel items={HOURS} index={hour} onChange={setHour} label="Hour" />
          <Text style={[styles.colon, { color: theme.text }]}>:</Text>
          <Wheel items={MINUTES} index={minute} onChange={setMinute} label="Minutes" />
          <Wheel items={PERIODS} index={period} onChange={setPeriod} label="AM or PM" />
        </View>

        <ThemedText
          type="small"
          style={[styles.note, { color: tooSoon || tooLate ? Brand.red : theme.textSecondary }]}>
          {tooSoon
            ? 'Pick a time at least 5 minutes from now.'
            : tooLate
              ? 'Pick a time within the next 24 hours.'
              : `${isTomorrow(chosen) ? 'Tomorrow' : 'Today'}, ${formatClock(chosen)}`}
        </ThemedText>
      </View>
    </Modal>
  );
}

/** One scrolling column. It snaps to rows; the row in the middle is chosen. */
function Wheel({
  items,
  index,
  onChange,
  label,
}: {
  items: string[];
  index: number;
  onChange: (index: number) => void;
  label: string;
}) {
  const theme = useTheme();
  const scroller = useRef<ScrollView>(null);
  const positioned = useRef(false);

  function handleScroll(event: NativeSyntheticEvent<NativeScrollEvent>) {
    const row = Math.round(event.nativeEvent.contentOffset.y / ITEM);
    const clamped = Math.max(0, Math.min(items.length - 1, row));
    if (clamped !== index) onChange(clamped);
  }

  return (
    <ScrollView
      ref={scroller}
      accessibilityLabel={`${label}: ${items[index]}`}
      style={styles.wheel}
      contentContainerStyle={styles.wheelContent}
      showsVerticalScrollIndicator={false}
      snapToInterval={ITEM}
      decelerationRate="fast"
      scrollEventThrottle={16}
      onScroll={handleScroll}
      // Start at the current choice (once, when it first appears).
      onLayout={() => {
        if (positioned.current) return;
        positioned.current = true;
        scroller.current?.scrollTo({ y: index * ITEM, animated: false });
      }}>
      {items.map((item, i) => (
        <Pressable
          key={item}
          onPress={() => scroller.current?.scrollTo({ y: i * ITEM, animated: true })}
          style={styles.row}>
          <Text
            style={[
              styles.rowText,
              { color: i === index ? theme.text : theme.textSecondary },
              i === index && styles.rowTextChosen,
            ]}>
            {item}
          </Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.35)',
  },
  sheet: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: Spacing.three,
    paddingHorizontal: Spacing.four,
    gap: Spacing.three,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
  },
  wheels: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: Spacing.two,
  },
  band: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: ITEM * Math.floor(VISIBLE / 2),
    height: ITEM,
    borderRadius: 12,
  },
  wheel: {
    height: ITEM * VISIBLE,
    width: 72,
    flexGrow: 0,
  },
  wheelContent: {
    paddingVertical: ITEM * Math.floor(VISIBLE / 2),
  },
  row: {
    height: ITEM,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowText: {
    fontSize: 20,
  },
  rowTextChosen: {
    fontSize: 24,
    fontWeight: 700,
  },
  colon: {
    fontSize: 24,
    fontWeight: 700,
  },
  note: {
    textAlign: 'center',
  },
});
