import Ionicons from '@expo/vector-icons/Ionicons';
import { useFocusEffect } from 'expo-router';
import { type ComponentProps, useCallback, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from 'react-native';

import { BigButton } from '@/components/big-button';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { fetchHistory, keepSession, type HistoryItem } from '@/services/server';
import { useSafety } from '@/state/safety-store';
import { formatClock, formatWhen } from '@/utils/time';

/**
 * Your past sessions and SOS alerts, newest first, read from the server (the
 * privacy rules only let you see your own).
 * - filter "all": every session and SOS (Session History)
 * - filter "alerts": only times your Circle was alerted: missed check-ins and
 *   SOS (Notifications tab)
 */
export function RecentActivity({ filter = 'all' }: { filter?: 'all' | 'alerts' }) {
  const { checkIn } = useSafety();
  const theme = useTheme();
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const history = await fetchHistory(filter === 'alerts' ? 50 : 20);
    setLoading(false);
    setFailed(history === null);
    if (history) setItems(history);
  }, [filter]);

  // Reload whenever this screen is opened, or a session starts or ends.
  const checkInKey = checkIn?.server?.id ?? null;
  useFocusEffect(
    useCallback(() => {
      load();
      // checkInKey isn't used inside, but listing it makes the list reload
      // when a session starts or ends while this screen is open.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [load, checkInKey]),
  );

  // "Keep 7 more days": push back when this session's data is deleted.
  const [keeping, setKeeping] = useState<string | null>(null);
  async function keep(id: string) {
    setKeeping(id);
    const deleteAfter = await keepSession(id);
    setKeeping(null);
    if (!deleteAfter) {
      Alert.alert("Couldn't keep it longer", 'Check your internet and try again.');
      return;
    }
    setItems(
      (current) =>
        current?.map((i) => (i.kind === 'check-in' && i.id === id ? { ...i, deleteAfter } : i)) ??
        null,
    );
  }

  const shown =
    filter === 'alerts'
      ? items?.filter((i) => i.kind === 'sos' || i.status === 'missed')
      : items;

  return (
    <View style={styles.section}>
      {failed && (
        <ThemedText type="small" style={{ color: Brand.red }}>
          Couldn&apos;t load. Check your internet and tap Refresh.
        </ThemedText>
      )}
      {items === null && loading && <ActivityIndicator color={Brand.green} />}
      {shown?.length === 0 && (
        <ThemedText type="small" themeColor="textSecondary">
          {filter === 'alerts'
            ? "No alerts. When a check-in is missed or you press SOS, you'll see it here."
            : 'Nothing yet. Your sessions and SOS alerts will appear here.'}
        </ThemedText>
      )}

      {shown?.map((item) => (
        <View
          key={`${item.kind}-${item.at}`}
          style={[styles.row, { backgroundColor: theme.backgroundElement, borderColor: theme.border }]}>
          <View style={[styles.iconCircle, { backgroundColor: iconBackground(item, theme.backgroundSelected) }]}>
            <Ionicons name={iconFor(item)} size={20} color={outcomeColor(item)} />
          </View>
          <View style={styles.texts}>
            <ThemedText type="smallBold">
              {item.kind === 'sos'
                ? 'SOS alert'
                : `${item.destination ? item.destination : 'Session'}, ETA ${formatClock(new Date(item.returnBy))}`}
            </ThemedText>
            <ThemedText type="small" style={{ color: outcomeColor(item) }}>
              {describeOutcome(item)}
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {formatWhen(new Date(item.at))}
              {item.kind === 'check-in' && item.hasPhoto ? ' · outfit photo' : ''}
            </ThemedText>
            {item.kind === 'check-in' && item.deleteAfter && (
              <View style={styles.keepRow}>
                <ThemedText type="small" themeColor="textSecondary">
                  Deleted {formatDay(new Date(item.deleteAfter))}
                </ThemedText>
                <Pressable
                  onPress={() => keep(item.id)}
                  disabled={keeping === item.id}
                  accessibilityRole="button"
                  hitSlop={Spacing.two}>
                  <ThemedText type="smallBold" style={{ color: Brand.green }}>
                    {keeping === item.id ? 'Keeping…' : 'Keep 7 more days'}
                  </ThemedText>
                </Pressable>
              </View>
            )}
          </View>
        </View>
      ))}

      <BigButton
        label={loading ? 'Loading…' : 'Refresh'}
        variant="outline"
        size="small"
        onPress={load}
        disabled={loading}
      />
    </View>
  );
}

// "Texted 1 of 1 [trial template] (John: …error…)" -> "texted 1 of 1".
function shortSummary(summary: string | null) {
  if (!summary) return null;
  if (summary === 'No one in Circle') return 'no one in Circle';
  return summary.replace(/\s*\[trial template\]/, '').replace(/\s*\(.*$/, '').toLowerCase();
}

// One line describing how it ended.
function describeOutcome(item: HistoryItem): string {
  if (item.kind === 'sos') {
    const texted = shortSummary(item.alertsSummary) ?? 'sending…';
    return `${capitalize(texted)} · ${item.hadLocation ? 'location shared' : 'no location'}`;
  }
  switch (item.status) {
    case 'active':
      return 'In progress';
    case 'safe':
      return item.endedAt ? `Safe at ${formatClock(new Date(item.endedAt))}` : 'Safe';
    case 'missed': {
      let text = 'Missed';
      const alerts = shortSummary(item.alertsSummary);
      if (alerts) text += `: Circle ${alerts}`;
      if (item.confirmedSafeAt) {
        const allClear = item.allClearSummary;
        text += ' · safe later';
        if (allClear?.startsWith('Texted')) text += `, all-clear ${shortSummary(allClear)}`;
        else if (allClear === 'Sending…') text += ', sending all-clear…';
      }
      return text;
    }
  }
}

function iconFor(item: HistoryItem): ComponentProps<typeof Ionicons>['name'] {
  if (item.kind === 'sos') return 'warning';
  if (item.status === 'active') return 'time-outline';
  if (item.status === 'missed') return item.confirmedSafeAt ? 'checkmark-done' : 'alert-circle';
  return 'checkmark-circle';
}

function outcomeColor(item: HistoryItem) {
  if (item.kind === 'sos') return Brand.red;
  if (item.status === 'missed' && !item.confirmedSafeAt) return Brand.red;
  return Brand.green;
}

function iconBackground(item: HistoryItem, soft: string) {
  return outcomeColor(item) === Brand.red ? '#FDECEC' : soft;
}

// "on Oct 31"
function formatDay(date: Date) {
  return `on ${date.toLocaleDateString([], { month: 'short', day: 'numeric' })}`;
}

function capitalize(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const styles = StyleSheet.create({
  section: {
    gap: Spacing.two,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    padding: Spacing.three,
    borderRadius: 18,
    borderWidth: 1,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  texts: {
    flex: 1,
    gap: 2,
  },
  keepRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: Spacing.two,
  },
});
