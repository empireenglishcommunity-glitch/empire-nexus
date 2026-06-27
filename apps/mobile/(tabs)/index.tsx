import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import {
  Keyboard,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import EmpireCard from '../../src/components/EmpireCard';
import EmpireLogo from '../../src/components/EmpireLogo';
import OrnamentDivider from '../../src/components/OrnamentDivider';
import RoyalBackground from '../../src/components/RoyalBackground';
import SectionLabel from '../../src/components/SectionLabel';
import SpeakerButton from '../../src/components/SpeakerButton';
import { FEATURED_WORDS, wordOfTheDay } from '../../src/data/dictionary';
import { searchCurated } from '../../src/services/dictionary';
import { getHistory } from '../../src/services/storage';
import { WordEntry, HistoryItem } from '../../src/data/types';
import { colors, radius, spacing } from '../../src/theme';

export default function HomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<WordEntry[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  const wotd = wordOfTheDay();

  useFocusEffect(
    useCallback(() => {
      let active = true;
      getHistory().then((h) => {
        if (active) setHistory(h);
      });
      return () => {
        active = false;
      };
    }, [])
  );

  const onChange = (text: string) => {
    setQuery(text);
    setSuggestions(searchCurated(text));
  };

  const openWord = (word: string) => {
    const w = word.trim();
    if (!w) return;
    Keyboard.dismiss();
    setQuery('');
    setSuggestions([]);
    router.push(`/word/${encodeURIComponent(w.toLowerCase())}`);
  };

  return (
    <RoyalBackground>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{
          paddingTop: insets.top + 16,
          paddingBottom: insets.bottom + 32,
          paddingHorizontal: spacing.lg,
        }}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <EmpireLogo size={48} />
          <View style={{ marginLeft: 12 }}>
            <Text style={styles.brand}>EMPIRE ENGLISH</Text>
            <Text style={styles.brandSub}>Speak like an Emperor</Text>
          </View>
        </View>

        {/* Search */}
        <View style={styles.searchRow}>
          <MaterialCommunityIcons name="magnify" size={22} color={colors.goldDeep} />
          <TextInput
            value={query}
            onChangeText={onChange}
            onSubmitEditing={() => openWord(query)}
            placeholder="Search any word..."
            placeholderTextColor={colors.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
            style={styles.input}
          />
          {query.length > 0 && (
            <Pressable onPress={() => onChange('')} hitSlop={10}>
              <MaterialCommunityIcons name="close-circle" size={20} color={colors.textFaint} />
            </Pressable>
          )}
        </View>

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <View style={styles.suggestions}>
            {suggestions.map((s) => (
              <Pressable
                key={s.word}
                onPress={() => openWord(s.word)}
                style={({ pressed }) => [styles.suggestRow, pressed && styles.suggestRowPressed]}
              >
                <Text style={styles.suggestWord}>{s.word}</Text>
                <Text style={styles.suggestPos}>{s.partOfSpeech}</Text>
              </Pressable>
            ))}
          </View>
        )}

        {/* Word of the Day */}
        {suggestions.length === 0 && (
          <>
            <SectionLabel text="Word of the Day" icon="white-balance-sunny" />
            <EmpireCard onPress={() => openWord(wotd.word)}>
              <View style={styles.wotdRow}>
                <View style={{ flex: 1, paddingRight: 12 }}>
                  <Text style={styles.wotdWord}>{wotd.word}</Text>
                  {wotd.ipaUS && <Text style={styles.ipa}>{wotd.ipaUS}</Text>}
                  <Text style={styles.arabic}>{wotd.arabic}</Text>
                </View>
                <SpeakerButton text={wotd.word} />
              </View>
            </EmpireCard>

            <OrnamentDivider />

            {/* Featured tiles */}
            <SectionLabel text="Imperial Vocabulary" icon="shield-crown" />
            <View style={styles.tileGrid}>
              {FEATURED_WORDS.map((w) => (
                <Pressable
                  key={w}
                  onPress={() => openWord(w)}
                  style={({ pressed }) => [styles.tile, pressed && styles.tilePressed]}
                >
                  <MaterialCommunityIcons name="crown-outline" size={18} color={colors.goldDeep} />
                  <Text style={styles.tileText}>{w}</Text>
                </Pressable>
              ))}
            </View>

            {/* History */}
            {history.length > 0 && (
              <>
                <OrnamentDivider />
                <SectionLabel text="Recently Viewed" icon="history" />
                {history.slice(0, 8).map((h) => (
                  <Pressable
                    key={h.word + h.at}
                    onPress={() => openWord(h.word)}
                    style={({ pressed }) => [styles.historyRow, pressed && styles.suggestRowPressed]}
                  >
                    <MaterialCommunityIcons name="clock-outline" size={16} color={colors.textFaint} />
                    <Text style={styles.historyWord}>{h.word}</Text>
                    <MaterialCommunityIcons name="chevron-right" size={18} color={colors.textFaint} />
                  </Pressable>
                ))}
              </>
            )}
          </>
        )}
      </ScrollView>
    </RoyalBackground>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xl },
  brand: { color: colors.gold, fontSize: 18, fontWeight: '800', letterSpacing: 2 },
  brandSub: { color: colors.textDim, fontSize: 12, fontWeight: '600', marginTop: 2 },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 16,
    paddingVertical: 4,
    marginBottom: spacing.lg,
  },
  input: {
    flex: 1,
    color: colors.text,
    fontSize: 16,
    paddingVertical: 12,
    marginLeft: 10,
  },
  suggestions: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  suggestRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  suggestRowPressed: { backgroundColor: colors.surfaceRaised },
  suggestWord: { color: colors.text, fontSize: 17, fontWeight: '700' },
  suggestPos: { color: colors.textFaint, fontSize: 13, fontStyle: 'italic' },
  wotdRow: { flexDirection: 'row', alignItems: 'center' },
  wotdWord: { color: colors.goldBright, fontSize: 28, fontWeight: '800' },
  ipa: { color: colors.textDim, fontSize: 15, marginTop: 2 },
  arabic: { color: colors.text, fontSize: 16, marginTop: 8, textAlign: 'right' },
  tileGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  tile: {
    width: '48%',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 16,
    paddingHorizontal: 14,
    marginBottom: 12,
  },
  tilePressed: { borderColor: colors.gold, backgroundColor: colors.surfaceRaised },
  tileText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginLeft: 10,
    textTransform: 'capitalize',
  },
  historyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 13,
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  historyWord: {
    flex: 1,
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 10,
    textTransform: 'capitalize',
  },
});
