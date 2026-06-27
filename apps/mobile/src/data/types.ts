/** Core data types for the Empire English dictionary. */

export interface Syllable {
  /** The syllable text, e.g. "em" */
  text: string;
  /** Whether this syllable carries the primary stress. */
  stressed?: boolean;
}

export interface WordEntry {
  /** The headword, lowercased, e.g. "empire". */
  word: string;
  /** Part of speech, e.g. "noun", "verb". */
  partOfSpeech?: string;
  /** US IPA transcription, e.g. "/ˈɛm.paɪr/". */
  ipaUS?: string;
  /** UK IPA transcription (where available). */
  ipaUK?: string;
  /** Syllable breakdown with stress marked. */
  syllables: Syllable[];
  /** Logical Arabic meaning (not a literal translation). */
  arabic: string;
  /** English definition. */
  definition: string;
  /** Example sentence using the word. */
  example: string;
  /** Source of the entry. */
  source?: 'curated' | 'online';
}

export interface HistoryItem {
  word: string;
  at: number; // timestamp
}
