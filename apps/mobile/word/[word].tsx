import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import EmpireCard from '../../src/components/EmpireCard';
import OrnamentDivider from '../../src/components/OrnamentDivider';
import RoyalBackground from '../../src/components/RoyalBackground';
import SectionLabel from '../../src/components/SectionLabel';
import SpeakerButton from '../../src/components/SpeakerButton';
import SyllableBreakdown from '../../src/components/SyllableBreakdown';
import { WordEntry } from '../../src/data/types';
import { lookupWord } from '../../src/services/dictionary';
import { speak } from '../../src/services/speech';
import { addToHistory, isBookmarked, toggleBookmark } from '../../src/services/storage';
import { translateToArabic } from '../../src/services/translation';
import { colors, radius, spacing } from '../../src/theme';

export default function WordDetailScreen() {
  const params = useLocalSearchParams<{ word: string }>();
  const word = (Array.isArray(params.word) ? params.word[0] : params.word) || '';
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [entry, setEntry] = useState<WordEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bookmarked, setBookmarked] = useState(false);
  const [arabic, setArabic] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setArabic(null);

    (async () => {
      const result = await lookupWord(word);
      if (!active) return;

      if (!result.entry) {
        setError(
          result.error === 'offline'
            ? 'This word is not in the imperial library, and you appear to be offline.'
            : `"${word}" was not found.`
        );
        setLoading(false);
        return;
      }

      setEntry(result.entry);
      setArabic(result.entry.arabic || null);
      setLoading(false);
      addToHistory(result.entry.word);
      isBookmarked(result.entry.word).then((b) => active && setBookmarked(b));

      // For online words without Arabic, attempt a translation.
      if (result.entry.source === 'online' && !result.entry.arabic) {
        const ar = await translateToArabic(result.entry.word);
        if (active && ar) setArabic(ar);
      }
    })();

    return () => {
      active = false;
    };
  }, [word]);

  const onToggleBookmark = async () => {
    if (!entry) return;
    const next = await toggleBookmark(entry.word);
    setBookmarked(next);
  };

  return (
    <RoyalBackground>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.topBar, { paddingTop: insets.top + 8 }]}>
        <Pressable onPress={() => router.back()} hitSlop={12} style={styles.iconBtn}>
          <MaterialCommunityIcons name="chevron-left" size={28} color={colors.gold} />
        </Pressable>
        {entry && (
          <Pressable onPress={onToggleBookmark} hitSlop={12} style={styles.iconBtn}>
            <MaterialCommunityIcons
              name={bookmarked ? 'bookmark' : 'bookmark-outline'}
              size={24}
              color={colors.gold}
            />
          </Pressable>
        )}
      </View>

      {loading ? (
        <View style={styles.centerFill}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.loadingText}>Consulting the archives…</Text>
        </View>
      ) : error ? (
        <View style={styles.centerFill}>
          <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.goldDeep} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : entry ? (
        <ScrollView
          contentContainerStyle={{ paddingBottom: insets.bottom + 32, paddingHorizontal: spacing.lg }}
          showsVerticalScrollIndicator={false}
        >
          {/* Headword + pronounce */}
          <View style={styles.headRow}>
            <View style={{ flex: 1, paddingRight: 12 }}>
              <Text style={styles.word}>{entry.word}</Text>
              {entry.partOfSpeech && <Text style={styles.pos}>{entry.partOfSpeech}</Text>}
            </View>
            <SpeakerButton text={entry.word} size={58} />
          </View>

          {/* Slow pronounce */}
          <Pressable
            onPress={() => speak(entry.word, { rate: 'slow' })}
            style={({ pressed }) => [styles.slowBtn, pressed && { opacity: 0.7 }]}
          >
            <MaterialCommunityIcons name="tortoise" size={18} color={colors.gold} />
            <Text style={styles.slowText}>Hear it slowly</Text>
          </Pressable>

          {entry.source === 'online' && (
            <View style={styles.onlineBadge}>
              <MaterialCommunityIcons name="web" size={13} color={colors.textFaint} />
              <Text style={styles.onlineText}>From online dictionary</Text>
            </View>
          )}

          <OrnamentDivider />

          {/* Syllables */}
          {entry.syllables.length > 0 && (
            <View style={styles.section}>
              <SectionLabel text="Syllables (tap to hear)" icon="music-note" />
              <SyllableBreakdown syllables={entry.syllables} />
            </View>
          )}

          {/* IPA */}
          {(entry.ipaUS || entry.ipaUK) && (
            <View style={styles.section}>
              <SectionLabel text="Pronunciation (IPA)" icon="alphabetical-variant" />
              <View style={styles.ipaRow}>
                {entry.ipaUS ? (
                  <View style={styles.ipaChip}>
                    <Text style={styles.ipaFlag}>US</Text>
                    <Text style={styles.ipaText}>{entry.ipaUS}</Text>
                  </View>
                ) : null}
                {entry.ipaUK ? (
                  <View style={styles.ipaChip}>
                    <Text style={styles.ipaFlag}>UK</Text>
                    <Text style={styles.ipaText}>{entry.ipaUK}</Text>
                  </View>
                ) : null}
              </View>
            </View>
          )}

          {/* Arabic meaning */}
          {arabic ? (
            <View style={styles.section}>
              <SectionLabel text="Logical Arabic Meaning" icon="translate" />
              <EmpireCard>
                <Text style={styles.arabic}>{arabic}</Text>
              </EmpireCard>
            </View>
          ) : null}

          {/* Definition */}
          {entry.definition ? (
            <View style={styles.section}>
              <SectionLabel text="Definition" icon="book-open-variant" />
              <Text style={styles.definition}>{entry.definition}</Text>
            </View>
          ) : null}

          {/* Example */}
          {entry.example ? (
            <View style={styles.section}>
              <SectionLabel text="Example" icon="comment-quote" />
              <EmpireCard>
                <View style={styles.exampleRow}>
                  <Text style={styles.example}>{entry.example}</Text>
                  <SpeakerButton text={entry.example} size={44} variant="ghost" />
                </View>
              </EmpireCard>
            </View>
          ) : null}
        </ScrollView>
      ) : null}
    </RoyalBackground>
  );
}

const styles = StyleSheet.create({
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingBottom: 4,
  },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  centerFill: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  loadingText: { color: colors.textDim, marginTop: 14, fontSize: 15 },
  errorText: { color: colors.textDim, marginTop: 14, fontSize: 16, textAlign: 'center', lineHeight: 24 },
  headRow: { flexDirection: 'row', alignItems: 'center', marginTop: 8 },
  word: { color: colors.goldBright, fontSize: 40, fontWeight: '800', textTransform: 'capitalize' },
  pos: { color: colors.textDim, fontSize: 16, fontStyle: 'italic', marginTop: 2 },
  slowBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    marginTop: 14,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  slowText: { color: colors.gold, fontSize: 14, fontWeight: '700', marginLeft: 8 },
  onlineBadge: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  onlineText: { color: colors.textFaint, fontSize: 12, marginLeft: 6 },
  section: { marginTop: 18 },
  ipaRow: { flexDirection: 'row', flexWrap: 'wrap' },
  ipaChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginRight: 10,
    marginBottom: 10,
  },
  ipaFlag: {
    color: colors.black,
    backgroundColor: colors.gold,
    fontSize: 11,
    fontWeight: '800',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    marginRight: 8,
    overflow: 'hidden',
  },
  ipaText: { color: colors.text, fontSize: 18, fontWeight: '600' },
  arabic: { color: colors.text, fontSize: 20, lineHeight: 32, textAlign: 'right' },
  definition: { color: colors.text, fontSize: 17, lineHeight: 26 },
  exampleRow: { flexDirection: 'row', alignItems: 'center' },
  example: { flex: 1, color: colors.text, fontSize: 16, lineHeight: 24, fontStyle: 'italic', paddingRight: 12 },
});
