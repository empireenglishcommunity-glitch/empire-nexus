import { DICTIONARY, DICTIONARY_MAP } from '../data/dictionary';
import { Syllable, WordEntry } from '../data/types';

/**
 * Dictionary lookup service.
 * Offline-first: curated entries win. Any other word falls back to
 * dictionaryapi.dev when the device is online.
 */

const API_BASE = 'https://api.dictionaryapi.dev/api/v2/entries/en/';

export interface LookupResult {
  entry: WordEntry | null;
  /** Whether the result came from the curated offline set. */
  offline: boolean;
  /** Set when an online lookup was attempted but failed. */
  error?: string;
}

/** Naive but useful syllable splitter for online words (no stress data). */
export function estimateSyllables(word: string): Syllable[] {
  const w = word.toLowerCase().trim();
  if (!w) return [];
  // Split around vowel groups; keep it forgiving.
  const matches = w.match(/[^aeiouy]*[aeiouy]+(?:[^aeiouy]*$|[^aeiouy](?=[^aeiouy]))?/gi);
  const parts = matches && matches.length > 0 ? matches : [w];
  return parts.map((text) => ({ text }));
}

/** Look up a word: curated first, then online fallback. */
export async function lookupWord(raw: string): Promise<LookupResult> {
  const word = raw.toLowerCase().trim();
  if (!word) return { entry: null, offline: true };

  const curated = DICTIONARY_MAP[word];
  if (curated) {
    return { entry: curated, offline: true };
  }

  // Online fallback.
  try {
    const res = await fetch(API_BASE + encodeURIComponent(word));
    if (!res.ok) {
      return { entry: null, offline: false, error: 'not-found' };
    }
    const data = await res.json();
    const first = Array.isArray(data) ? data[0] : null;
    if (!first) return { entry: null, offline: false, error: 'not-found' };

    const phonetic: string | undefined =
      first.phonetic ||
      (Array.isArray(first.phonetics)
        ? first.phonetics.find((p: any) => p?.text)?.text
        : undefined);

    const meaning = Array.isArray(first.meanings) ? first.meanings[0] : null;
    const def = meaning?.definitions?.[0];

    const entry: WordEntry = {
      word,
      partOfSpeech: meaning?.partOfSpeech,
      ipaUS: phonetic,
      syllables: estimateSyllables(word),
      arabic: '', // filled by translation service when online
      definition: def?.definition || 'No definition available.',
      example: def?.example || '',
      source: 'online',
    };
    return { entry, offline: false };
  } catch (e) {
    return { entry: null, offline: false, error: 'offline' };
  }
}

/** Local prefix/substring search over the curated dictionary. */
export function searchCurated(query: string, limit = 8): WordEntry[] {
  const q = query.toLowerCase().trim();
  if (!q) return [];
  const starts = DICTIONARY.filter((e) => e.word.startsWith(q));
  const contains = DICTIONARY.filter(
    (e) => !e.word.startsWith(q) && e.word.includes(q)
  );
  return [...starts, ...contains].slice(0, limit);
}

export const DictionaryService = { lookupWord, searchCurated, estimateSyllables };
export default DictionaryService;
