import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { speak } from '../services/speech';
import { Syllable } from '../data/types';
import { colors, radius } from '../theme';

interface Props {
  syllables: Syllable[];
  /** Speak each syllable on tap (uses slow rate for clarity). */
  tappable?: boolean;
}

/**
 * Renders syllables as gold chips, highlighting the stressed one.
 * Tapping a syllable pronounces it slowly.
 */
export default function SyllableBreakdown({ syllables, tappable = true }: Props) {
  if (!syllables || syllables.length === 0) return null;

  return (
    <View style={styles.row}>
      {syllables.map((syl, i) => {
        const chip = (
          <View style={[styles.chip, syl.stressed && styles.chipStressed]}>
            <Text style={[styles.text, syl.stressed && styles.textStressed]}>
              {syl.text}
            </Text>
            {syl.stressed && <View style={styles.stressDot} />}
          </View>
        );

        if (!tappable) {
          return <View key={`${syl.text}-${i}`}>{chip}</View>;
        }
        return (
          <Pressable
            key={`${syl.text}-${i}`}
            onPress={() => speak(syl.text, { rate: 'slow' })}
            style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}
          >
            {chip}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: 8,
    marginBottom: 8,
    alignItems: 'center',
  },
  chipStressed: {
    borderColor: colors.gold,
    backgroundColor: 'rgba(212,175,55,0.14)',
  },
  text: {
    color: colors.textDim,
    fontSize: 18,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  textStressed: {
    color: colors.goldBright,
    fontWeight: '800',
  },
  stressDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.gold,
    marginTop: 4,
  },
});
