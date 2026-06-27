import { MaterialCommunityIcons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme';

interface Props {
  text: string;
  icon?: keyof typeof MaterialCommunityIcons.glyphMap;
}

/** Small, uppercase, gold section heading with optional icon. */
export default function SectionLabel({ text, icon }: Props) {
  return (
    <View style={styles.row}>
      {icon && (
        <MaterialCommunityIcons
          name={icon}
          size={15}
          color={colors.goldDeep}
          style={styles.icon}
        />
      )}
      <Text style={styles.text}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  icon: { marginRight: 6 },
  text: {
    color: colors.goldDeep,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 2.5,
    textTransform: 'uppercase',
  },
});
