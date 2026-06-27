/**
 * Empire English Community — Imperial Design System
 * Gold-on-black, derived from the brand emblem.
 */

export const colors = {
  // Black canvas
  black: '#0A0A0B',
  blackSoft: '#101015',
  ink: '#16161C',
  surface: '#1A1A22',
  surfaceRaised: '#22222C',
  border: '#2C2C38',

  // Imperial gold
  gold: '#D4AF37',
  goldBright: '#F4D27A',
  goldDeep: '#B8860B',
  goldMuted: '#8C7A3A',

  // Text
  text: '#F5EFD8',
  textDim: '#B9B19A',
  textFaint: '#7A7464',

  // Accents
  crimson: '#7C1F2B',
  emerald: '#2E6E4E',
  white: '#FFFFFF',

  // Utility
  overlay: 'rgba(0,0,0,0.55)',
  goldGlow: 'rgba(212,175,55,0.18)',
} as const;

export const gradients = {
  // Black canvas gradient (top -> bottom)
  royal: ['#0A0A0B', '#121018', '#0A0A0B'] as const,
  // Gold sheen for buttons / emblems
  gold: ['#F4D27A', '#D4AF37', '#B8860B'] as const,
  goldSoft: ['#D4AF37', '#9C7C1F'] as const,
  // Card sheen
  card: ['#22222C', '#16161C'] as const,
  // Splash gate
  gate: ['#000000', '#14110A', '#000000'] as const,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  xl: 28,
  pill: 999,
} as const;

export const typography = {
  hero: { fontSize: 34, fontWeight: '800' as const, letterSpacing: 1 },
  title: { fontSize: 26, fontWeight: '800' as const, letterSpacing: 0.5 },
  heading: { fontSize: 20, fontWeight: '700' as const, letterSpacing: 0.3 },
  body: { fontSize: 16, fontWeight: '500' as const },
  label: { fontSize: 13, fontWeight: '700' as const, letterSpacing: 2 },
  caption: { fontSize: 12, fontWeight: '500' as const },
  arabic: { fontSize: 20, fontWeight: '600' as const },
} as const;

export const shadow = {
  gold: {
    shadowColor: colors.gold,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 14,
    elevation: 8,
  },
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 6,
  },
} as const;

export const theme = { colors, gradients, spacing, radius, typography, shadow };
export default theme;
