import { MaterialCommunityIcons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import { colors } from '../theme';

interface Props {
  style?: ViewStyle;
}

/** Decorative gold divider with a central diamond ornament. */
export default function OrnamentDivider({ style }: Props) {
  return (
    <View style={[styles.row, style]}>
      <View style={styles.line} />
      <MaterialCommunityIcons name="rhombus-outline" size={12} color={colors.gold} />
      <View style={styles.line} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 14,
  },
  line: {
    height: 1,
    width: 60,
    backgroundColor: colors.goldMuted,
    marginHorizontal: 10,
    opacity: 0.6,
  },
});
