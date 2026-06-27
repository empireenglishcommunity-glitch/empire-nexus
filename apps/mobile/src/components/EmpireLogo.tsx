import { MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, gradients, shadow } from '../theme';

interface Props {
  size?: number;
  showWordmark?: boolean;
}

/** The brand emblem: a gold crown inside a glowing imperial ring. */
export default function EmpireLogo({ size = 96, showWordmark = false }: Props) {
  const ring = size;
  const inner = size * 0.78;
  return (
    <View style={styles.wrap}>
      <View style={[styles.ringOuter, shadow.gold, { width: ring, height: ring, borderRadius: ring / 2 }]}>
        <LinearGradient
          colors={gradients.gold}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[styles.ring, { width: ring, height: ring, borderRadius: ring / 2 }]}
        >
          <View
            style={[
              styles.inner,
              { width: inner, height: inner, borderRadius: inner / 2 },
            ]}
          >
            <MaterialCommunityIcons name="crown" size={inner * 0.5} color={colors.gold} />
          </View>
        </LinearGradient>
      </View>
      {showWordmark && (
        <View style={styles.wordmark}>
          <Text style={styles.brandTop}>EMPIRE ENGLISH</Text>
          <Text style={styles.brandSub}>COMMUNITY</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center' },
  ringOuter: { alignItems: 'center', justifyContent: 'center' },
  ring: { alignItems: 'center', justifyContent: 'center' },
  inner: {
    backgroundColor: colors.black,
    alignItems: 'center',
    justifyContent: 'center',
  },
  wordmark: { marginTop: 14, alignItems: 'center' },
  brandTop: {
    color: colors.gold,
    fontSize: 22,
    fontWeight: '800',
    letterSpacing: 3,
  },
  brandSub: {
    color: colors.textDim,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 8,
    marginTop: 2,
  },
});
