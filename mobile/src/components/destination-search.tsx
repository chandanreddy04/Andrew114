import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Keyboard, Pressable, StyleSheet, View } from 'react-native';

import { TextInput } from '@/components/text';
import { ThemedText } from '@/components/themed-text';
import { Brand, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { getRoughLocation } from '@/services/location';
import {
  fetchPlaceDetails,
  searchPlaces,
  type MapPosition,
  type Place,
} from '@/services/server';

// Wait this long after the last letter before searching.
const PAUSE_MS = 400;
const MIN_LETTERS = 3;

/** "Olive Garden, 2001 South Lamar Boulevard, Austin, Texas 78745" */
function placeText(name: string, address: string) {
  const short = address.replace(/, USA$/, '');
  if (!short || short === name) return name;
  // An address result is already the whole address ("2001 S Lamar Blvd, Austin…").
  return short.startsWith(name) ? short : `${name}, ${short}`;
}

// A new id for each round of typing and picking (Google bills it as one search).
function newSession() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * "Where are you going?": type a place, then pick the real address from the
 * matches (Google Places, or OpenStreetMap if the server has no Google key).
 * Picking one also saves where it is on the map, so your Circle can open it
 * in Google Maps. You can also keep what you typed.
 */
export function DestinationSearch({
  value,
  place,
  onChange,
}: {
  value: string;
  place: MapPosition | null;
  onChange: (text: string, place: MapPosition | null) => void;
}) {
  const theme = useTheme();
  const [query, setQuery] = useState(''); // what was typed since the last pick
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  // The result being looked up after a tap (Google gives its position then).
  const [picking, setPicking] = useState<string | null>(null);
  const session = useRef<string | null>(null);

  // Where you are (only if location is already allowed), for nearby places first.
  const near = useRef<MapPosition | null>(null);
  useEffect(() => {
    getRoughLocation().then((position) => {
      near.current = position;
    });
  }, []);

  // Search once typing pauses; ignore answers to older searches.
  const latest = useRef(0);
  useEffect(() => {
    const text = query.trim();
    if (text.length < MIN_LETTERS) return;
    const timer = setTimeout(async () => {
      const id = ++latest.current;
      setSearching(true);
      session.current ??= newSession();
      const found = await searchPlaces(text, near.current, session.current);
      if (id !== latest.current) return;
      setResults(found);
      setSearched(true);
      setSearching(false);
    }, PAUSE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  function type(text: string) {
    latest.current++; // drop any search still on its way
    setQuery(text);
    setResults([]);
    setSearched(false);
    setSearching(false);
    onChange(text, null);
  }

  async function pick(picked: Place) {
    latest.current++;
    let { address, latitude, longitude } = picked;
    if ((latitude === null || longitude === null) && picked.place_id) {
      setPicking(picked.place_id);
      const details = await fetchPlaceDetails(picked.place_id, session.current ?? newSession());
      setPicking(null);
      if (details) ({ address, latitude, longitude } = details);
    }
    session.current = null; // the next search is a new one
    setQuery('');
    setResults([]);
    setSearched(false);
    const position =
      latitude !== null && longitude !== null ? { latitude, longitude } : null;
    onChange(placeText(picked.name, address), position);
    Keyboard.dismiss();
  }

  const field = { backgroundColor: theme.backgroundElement, borderColor: theme.border };
  const showList = query.trim().length >= MIN_LETTERS && (searching || searched);

  return (
    <View style={styles.wrap}>
      <View style={[styles.pill, field]}>
        <Ionicons
          name={place ? 'location' : 'location-outline'}
          size={22}
          color={place ? Brand.green : theme.textSecondary}
        />
        <TextInput
          value={value}
          onChangeText={type}
          placeholder="Search a place or address"
          placeholderTextColor={theme.textSecondary}
          maxLength={255}
          returnKeyType="done"
          autoCorrect={false}
          style={[styles.input, { color: theme.text }]}
        />
        {value !== '' && (
          <Pressable
            onPress={() => type('')}
            accessibilityRole="button"
            accessibilityLabel="Clear destination"
            hitSlop={Spacing.two}>
            <Ionicons name="close-circle" size={22} color={theme.textSecondary} />
          </Pressable>
        )}
      </View>

      {showList && (
        <View style={[styles.list, field]}>
          {searching && results.length === 0 ? (
            <View style={styles.message}>
              <ActivityIndicator color={Brand.green} />
              <ThemedText type="small" themeColor="textSecondary">
                Searching…
              </ThemedText>
            </View>
          ) : results.length === 0 ? (
            <ThemedText type="small" themeColor="textSecondary" style={styles.message}>
              No matching addresses. You can keep what you typed.
            </ThemedText>
          ) : (
            results.map((result, i) => (
              <Pressable
                key={result.place_id ?? `${result.latitude},${result.longitude},${result.name}`}
                onPress={() => pick(result)}
                disabled={picking !== null}
                accessibilityRole="button"
                accessibilityLabel={placeText(result.name, result.address)}
                style={({ pressed }) => [
                  styles.row,
                  i > 0 && { borderTopWidth: 1, borderTopColor: theme.border },
                  pressed && { backgroundColor: theme.backgroundSelected },
                ]}>
                {picking !== null && picking === result.place_id ? (
                  <ActivityIndicator color={Brand.green} />
                ) : (
                  <Ionicons name="location-outline" size={20} color={Brand.green} />
                )}
                <View style={styles.rowText}>
                  <ThemedText type="smallBold" numberOfLines={1}>
                    {result.name}
                  </ThemedText>
                  {result.address !== '' && (
                    <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>
                      {result.address}
                    </ThemedText>
                  )}
                </View>
              </Pressable>
            ))
          )}
          {results.length > 0 && (
            <ThemedText type="small" themeColor="textSecondary" style={styles.credit}>
              {results[0].source === 'google'
                ? 'Powered by Google'
                : '© OpenStreetMap contributors'}
            </ThemedText>
          )}
        </View>
      )}

      {place && (
        <ThemedText type="small" themeColor="textSecondary">
          Your Circle can open this address on a map if an alert triggers.
        </ThemedText>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: Spacing.two,
  },
  pill: {
    borderRadius: 999,
    borderWidth: 1,
    minHeight: 60,
    paddingHorizontal: Spacing.four,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
  },
  input: {
    flex: 1,
    fontSize: 18,
    paddingVertical: Spacing.three,
  },
  list: {
    borderRadius: 20,
    borderWidth: 1,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.four,
  },
  rowText: {
    flex: 1,
  },
  credit: {
    fontSize: 12,
    textAlign: 'right',
    paddingHorizontal: Spacing.four,
    paddingBottom: Spacing.two,
  },
  message: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    padding: Spacing.four,
  },
});
