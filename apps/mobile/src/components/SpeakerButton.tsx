import { MaterialCommunityIcons } from '@expo/vector-icons';
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { speak, SpeechRate } from '../services/speech';
import { colors, shadow } from '../theme';

interface Props {
  text: string;
  rate?: SpeechRate;
  size?: number;
  /** Subtle (outline) or prominent (filled gold). */
  variant?: 'solid' | 'ghost';
}

/** Round button that pronounces the given text and pulses while speaking. */
export default function SpeakerButton({
  text,
  rate = 'normal',
  size = 52,
  variant = 'solid',
}: Props) {
  const [speaking, setSpeaking] = useState(false);
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let loop: Animated.CompositeAnimation | null = null;
    if (speaking) {
      loop = Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1, duration: 600, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 0, duration: 600, useNativeDriver: true }),
        ])
      );
      loop.start();
    } else {
      pulse.stopAnimation();
      pulse.setValue(0);
    }
    return () => {
      loop?.stop();
    };
  }, [speaking, pulse]);

  const onPress = () => {
    setSpeaking(true);
    speak(text, {
      rate,
      onDone: () => setSpeaking(false),
      onError: () => setSpeaking(false),
    });
  };

  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.18] });
  const ringOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.0, 0.5] });
  const isGhost = variant === 'ghost';

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Animated.View
        pointerEvents="none"
        style={[
          styles.ring,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            opacity: ringOpacity,
            transform: [{ scale }],
          },
        ]}
      />
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [
          styles.btn,
          isGhost ? styles.ghost : styles.solid,
          !isGhost && shadow.gold,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            opacity: pressed ? 0.85 : 1,
          },
        ]}
      >
        <MaterialCommunityIcons
          name={speaking ? 'volume-high' : 'volume-medium'}
          size={size * 0.46}
          color={isGhost ? colors.gold : colors.black}
        />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  ring: {
    position: 'absolute',
    backgroundColor: colors.gold,
  },
  btn: { alignItems: 'center', justifyContent: 'center' },
  solid: { backgroundColor: colors.gold },
  ghost: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: colors.gold,
  },
});
