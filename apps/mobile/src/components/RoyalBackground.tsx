import { LinearGradient } from 'expo-linear-gradient';
import React from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import { colors, gradients } from '../theme';

interface Props {
  children?: React.ReactNode;
  style?: ViewStyle;
  variant?: 'royal' | 'gate';
}

/** Full-screen black canvas with a subtle imperial gradient + gold glow corners. */
export default function RoyalBackground({ children, style, variant = 'royal' }: Props) {
  const palette = variant === 'gate' ? gradients.gate : gradients.royal;
  return (
    <LinearGradient colors={palette} style={[styles.fill, style]}>
      <View pointerEvents="none" style={[styles.glow, styles.glowTop]} />
      <View pointerEvents="none" style={[styles.glow, styles.glowBottom]} />
      {children}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
    backgroundColor: colors.black,
  },
  glow: {
    position: 'absolute',
    width: 320,
    height: 320,
    borderRadius: 320,
    backgroundColor: colors.goldGlow,
    opacity: 0.5,
  },
  glowTop: {
    top: -160,
    right: -120,
  },
  glowBottom: {
    bottom: -180,
    left: -140,
  },
});
