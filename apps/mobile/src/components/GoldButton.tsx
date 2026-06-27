import { MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from 'react-native';
import { colors, gradients, radius, shadow } from '../theme';

interface Props {
  label: string;
  onPress?: () => void;
  icon?: keyof typeof MaterialCommunityIcons.glyphMap;
  variant?: 'solid' | 'outline';
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
}

/** Primary imperial call-to-action button. */
export default function GoldButton({
  label,
  onPress,
  icon,
  variant = 'solid',
  loading = false,
  disabled = false,
  style,
}: Props) {
  const isOutline = variant === 'outline';
  const content = (
    <>
      {loading ? (
        <ActivityIndicator color={isOutline ? colors.gold : colors.black} />
      ) : (
        <>
          {icon && (
            <MaterialCommunityIcons
              name={icon}
              size={20}
              color={isOutline ? colors.gold : colors.black}
              style={styles.icon}
            />
          )}
          <Text style={[styles.label, isOutline && styles.labelOutline]}>{label}</Text>
        </>
      )}
    </>
  );

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        !isOutline && shadow.gold,
        { opacity: disabled ? 0.5 : pressed ? 0.85 : 1 },
        style,
      ]}
    >
      {isOutline ? (
        <View style={[styles.fill, styles.outline]}>{content}</View>
      ) : (
        <LinearGradient
          colors={gradients.gold}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.fill}
        >
          {content}
        </LinearGradient>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { borderRadius: radius.pill, overflow: 'hidden' },
  fill: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: radius.pill,
  },
  outline: {
    borderWidth: 1.5,
    borderColor: colors.gold,
    backgroundColor: 'transparent',
  },
  icon: { marginRight: 8 },
  label: {
    color: colors.black,
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  labelOutline: { color: colors.gold },
});
