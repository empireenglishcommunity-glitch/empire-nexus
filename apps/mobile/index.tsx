import { useRouter } from 'expo-router';
import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import EmpireLogo from '../src/components/EmpireLogo';
import GoldButton from '../src/components/GoldButton';
import OrnamentDivider from '../src/components/OrnamentDivider';
import RoyalBackground from '../src/components/RoyalBackground';
import { colors } from '../src/theme';

/** Cinematic imperial gate (splash) with the brand emblem + MacLempire sponsorship. */
export default function GateScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const logoScale = useRef(new Animated.Value(0.6)).current;
  const logoOpacity = useRef(new Animated.Value(0)).current;
  const textOpacity = useRef(new Animated.Value(0)).current;
  const ctaOpacity = useRef(new Animated.Value(0)).current;
  const ctaTranslate = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    Animated.sequence([
      Animated.parallel([
        Animated.timing(logoOpacity, {
          toValue: 1,
          duration: 700,
          useNativeDriver: true,
        }),
        Animated.spring(logoScale, {
          toValue: 1,
          friction: 6,
          tension: 60,
          useNativeDriver: true,
        }),
      ]),
      Animated.timing(textOpacity, {
        toValue: 1,
        duration: 600,
        easing: Easing.out(Easing.ease),
        useNativeDriver: true,
      }),
      Animated.parallel([
        Animated.timing(ctaOpacity, { toValue: 1, duration: 500, useNativeDriver: true }),
        Animated.timing(ctaTranslate, { toValue: 0, duration: 500, useNativeDriver: true }),
      ]),
    ]).start();
  }, [logoOpacity, logoScale, textOpacity, ctaOpacity, ctaTranslate]);

  const enter = () => router.replace('/(tabs)');

  return (
    <RoyalBackground variant="gate">
      <View style={[styles.container, { paddingTop: insets.top + 40, paddingBottom: insets.bottom + 28 }]}>
        <View style={styles.center}>
          <Animated.View style={{ opacity: logoOpacity, transform: [{ scale: logoScale }] }}>
            <EmpireLogo size={128} />
          </Animated.View>

          <Animated.View style={{ opacity: textOpacity, alignItems: 'center' }}>
            <Text style={styles.brand}>EMPIRE ENGLISH</Text>
            <Text style={styles.brandSub}>COMMUNITY</Text>
            <OrnamentDivider />
            <Text style={styles.tagline}>Speak like an Emperor.</Text>
          </Animated.View>
        </View>

        <Animated.View
          style={[styles.footer, { opacity: ctaOpacity, transform: [{ translateY: ctaTranslate }] }]}
        >
          <GoldButton label="Enter the Empire" icon="login-variant" onPress={enter} />
          <Text style={styles.sponsor}>Sponsored by MacLempire</Text>
        </Animated.View>
      </View>
    </RoyalBackground>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, paddingHorizontal: 28, justifyContent: 'space-between' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  brand: {
    color: colors.gold,
    fontSize: 30,
    fontWeight: '800',
    letterSpacing: 4,
    marginTop: 28,
  },
  brandSub: {
    color: colors.textDim,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 10,
    marginTop: 4,
  },
  tagline: {
    color: colors.text,
    fontSize: 16,
    fontStyle: 'italic',
    fontWeight: '500',
  },
  footer: { alignItems: 'center' },
  sponsor: {
    color: colors.textFaint,
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1,
    marginTop: 16,
  },
});
