import { MaterialCommunityIcons } from '@expo/vector-icons';
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import EmpireCard from '../../src/components/EmpireCard';
import GoldButton from '../../src/components/GoldButton';
import OrnamentDivider from '../../src/components/OrnamentDivider';
import RoyalBackground from '../../src/components/RoyalBackground';
import SectionLabel from '../../src/components/SectionLabel';
import { speak, SpeechRate } from '../../src/services/speech';
import { translateToArabic } from '../../src/services/translation';
import { colors, radius, spacing } from '../../src/theme';

const PRESETS = [
  'Speak like an emperor, and the world will listen.',
  'Discipline today shapes your destiny tomorrow.',
  'A wise leader listens before he speaks.',
  'Fortune favors the prepared mind.',
  'Every empire begins with a single brave step.',
];

export default function SentenceScreen() {
  const insets = useSafeAreaInsets();
  const [text, setText] = useState(PRESETS[0]);
  const [rate, setRate] = useState<SpeechRate>('normal');
  const [arabic, setArabic] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);

  const onSpeak = () => {
    if (text.trim()) speak(text, { rate });
  };

  const onTranslate = async () => {
    if (!text.trim()) return;
    setTranslating(true);
    setArabic(null);
    const result = await translateToArabic(text);
    setArabic(result ?? '⚠️ Translation needs an internet connection.');
    setTranslating(false);
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
        <Text style={styles.title}>Sentence Studio</Text>
        <Text style={styles.subtitle}>
          A word inside a sentence sounds different from the word alone. Hear it in context.
        </Text>

        <OrnamentDivider />

        <SectionLabel text="Your Sentence" icon="pencil" />
        <EmpireCard padded>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Type a sentence to pronounce..."
            placeholderTextColor={colors.textFaint}
            multiline
            style={styles.input}
          />
        </EmpireCard>

        {/* Speed control */}
        <View style={styles.speedRow}>
          <Text style={styles.speedLabel}>SPEED</Text>
          <View style={styles.segment}>
            {(['slow', 'normal'] as SpeechRate[]).map((r) => (
              <Pressable
                key={r}
                onPress={() => setRate(r)}
                style={[styles.segmentBtn, rate === r && styles.segmentBtnActive]}
              >
                <MaterialCommunityIcons
                  name={r === 'slow' ? 'tortoise' : 'rabbit'}
                  size={16}
                  color={rate === r ? colors.black : colors.textDim}
                />
                <Text style={[styles.segmentText, rate === r && styles.segmentTextActive]}>
                  {r === 'slow' ? 'Slow' : 'Normal'}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        <GoldButton label="Pronounce" icon="volume-high" onPress={onSpeak} style={{ marginTop: 8 }} />
        <GoldButton
          label="Logical Arabic Meaning"
          icon="translate"
          variant="outline"
          onPress={onTranslate}
          style={{ marginTop: 12 }}
        />

        {(translating || arabic) && (
          <EmpireCard style={{ marginTop: 16 }}>
            {translating ? (
              <View style={styles.translatingRow}>
                <ActivityIndicator color={colors.gold} />
                <Text style={styles.translatingText}>Translating…</Text>
              </View>
            ) : (
              <Text style={styles.arabicText}>{arabic}</Text>
            )}
          </EmpireCard>
        )}

        <OrnamentDivider />

        <SectionLabel text="Imperial Phrases" icon="format-quote-open" />
        {PRESETS.map((p) => (
          <Pressable
            key={p}
            onPress={() => {
              setText(p);
              setArabic(null);
              speak(p, { rate });
            }}
            style={({ pressed }) => [styles.presetRow, pressed && styles.presetPressed]}
          >
            <MaterialCommunityIcons name="volume-medium" size={18} color={colors.gold} />
            <Text style={styles.presetText}>{p}</Text>
          </Pressable>
        ))}
      </ScrollView>
    </RoyalBackground>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.gold, fontSize: 26, fontWeight: '800', letterSpacing: 0.5 },
  subtitle: { color: colors.textDim, fontSize: 14, marginTop: 6, lineHeight: 20 },
  input: {
    color: colors.text,
    fontSize: 18,
    lineHeight: 26,
    minHeight: 90,
    textAlignVertical: 'top',
  },
  speedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 18,
  },
  speedLabel: { color: colors.goldDeep, fontSize: 12, fontWeight: '800', letterSpacing: 2 },
  segment: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 3,
  },
  segmentBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: radius.pill,
  },
  segmentBtnActive: { backgroundColor: colors.gold },
  segmentText: { color: colors.textDim, fontSize: 14, fontWeight: '700', marginLeft: 6 },
  segmentTextActive: { color: colors.black },
  translatingRow: { flexDirection: 'row', alignItems: 'center' },
  translatingText: { color: colors.textDim, marginLeft: 10, fontSize: 15 },
  arabicText: { color: colors.text, fontSize: 20, lineHeight: 32, textAlign: 'right' },
  presetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  presetPressed: { opacity: 0.7 },
  presetText: { flex: 1, color: colors.text, fontSize: 15, lineHeight: 21, marginLeft: 12 },
});
