import { DICTIONARY_MAP } from '../data/dictionary';

/**
 * Translation service.
 *
 * Curated words ship with a hand-written, *logical* Arabic meaning (offline).
 * For online words and arbitrary sentences, we fall back to a free
 * translation endpoint when the device is online. It degrades gracefully:
 * if anything fails, we simply return null and the UI hides the Arabic block.
 */

// Google's lightweight unofficial endpoint; no key required. Best-effort only.
const GT_BASE =
  'https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=en&tl=ar&q=';

/** Get the curated Arabic meaning for a word, if any (offline). */
export function curatedArabic(word: string): string | null {
  const entry = DICTIONARY_MAP[word.toLowerCase().trim()];
  return entry?.arabic ?? null;
}

/** Best-effort online English -> Arabic translation. Returns null on failure. */
export async function translateToArabic(text: string): Promise<string | null> {
  const clean = text?.trim();
  if (!clean) return null;

  // Prefer the curated meaning for single curated words.
  const curated = curatedArabic(clean);
  if (curated) return curated;

  try {
    const res = await fetch(GT_BASE + encodeURIComponent(clean));
    if (!res.ok) return null;
    const data = await res.json();
    // Response shape: [[["translated","source",...], ...], ...]
    if (Array.isArray(data) && Array.isArray(data[0])) {
      const joined = data[0]
        .map((seg: any) => (Array.isArray(seg) ? seg[0] : ''))
        .join('');
      return joined?.trim() || null;
    }
    return null;
  } catch {
    return null;
  }
}

export const TranslationService = { curatedArabic, translateToArabic };
export default TranslationService;
