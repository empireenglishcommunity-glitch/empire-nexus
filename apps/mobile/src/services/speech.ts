import * as Speech from 'expo-speech';

/**
 * Speech layer.
 *
 * Phase 1 uses the on-device American-accent voice via expo-speech (offline).
 * It is intentionally isolated so a premium online "Authentic Voice" (neural TTS)
 * can be slotted in later without touching the screens.
 */

export type SpeechRate = 'slow' | 'normal';

const RATE_MAP: Record<SpeechRate, number> = {
  // expo-speech rate: 1.0 is the platform default.
  slow: 0.55,
  normal: 0.95,
};

const LANGUAGE_US = 'en-US';

let lastSpoken: string | null = null;

export interface SpeakOptions {
  rate?: SpeechRate;
  language?: string;
  onStart?: () => void;
  onDone?: () => void;
  onError?: (e: unknown) => void;
}

/** Speak a word or full sentence with the American accent. */
export function speak(text: string, options: SpeakOptions = {}): void {
  const clean = text?.trim();
  if (!clean) return;

  const { rate = 'normal', language = LANGUAGE_US, onStart, onDone, onError } = options;

  // Stop any current utterance so taps feel responsive.
  Speech.stop();
  lastSpoken = clean;

  Speech.speak(clean, {
    language,
    rate: RATE_MAP[rate],
    pitch: 1.0,
    onStart,
    onDone,
    onStopped: onDone,
    onError,
  });
}

/** Convenience: speak at slow speed. */
export function speakSlow(text: string, options: Omit<SpeakOptions, 'rate'> = {}): void {
  speak(text, { ...options, rate: 'slow' });
}

/** Stop any ongoing speech. */
export function stop(): void {
  Speech.stop();
}

/** Whether the engine is currently speaking. */
export async function isSpeaking(): Promise<boolean> {
  try {
    return await Speech.isSpeakingAsync();
  } catch {
    return false;
  }
}

export function getLastSpoken(): string | null {
  return lastSpoken;
}

export const SpeechService = { speak, speakSlow, stop, isSpeaking, getLastSpoken };
export default SpeechService;
