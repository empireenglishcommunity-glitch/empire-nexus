import AsyncStorage from '@react-native-async-storage/async-storage';
import { HistoryItem } from '../data/types';

/**
 * Local, offline storage for history and bookmarks.
 */

const KEY_HISTORY = '@empire/history';
const KEY_BOOKMARKS = '@empire/bookmarks';
const MAX_HISTORY = 50;

async function readJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

async function writeJSON(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore write errors silently
  }
}

/* ----------------------------- History ----------------------------- */

export async function getHistory(): Promise<HistoryItem[]> {
  return readJSON<HistoryItem[]>(KEY_HISTORY, []);
}

export async function addToHistory(word: string): Promise<HistoryItem[]> {
  const w = word.toLowerCase().trim();
  if (!w) return getHistory();
  const current = await getHistory();
  const filtered = current.filter((item) => item.word !== w);
  const next: HistoryItem[] = [{ word: w, at: Date.now() }, ...filtered].slice(
    0,
    MAX_HISTORY
  );
  await writeJSON(KEY_HISTORY, next);
  return next;
}

export async function clearHistory(): Promise<void> {
  await writeJSON(KEY_HISTORY, []);
}

/* ---------------------------- Bookmarks ---------------------------- */

export async function getBookmarks(): Promise<string[]> {
  return readJSON<string[]>(KEY_BOOKMARKS, []);
}

export async function isBookmarked(word: string): Promise<boolean> {
  const w = word.toLowerCase().trim();
  const list = await getBookmarks();
  return list.includes(w);
}

export async function toggleBookmark(word: string): Promise<boolean> {
  const w = word.toLowerCase().trim();
  if (!w) return false;
  const list = await getBookmarks();
  const exists = list.includes(w);
  const next = exists ? list.filter((x) => x !== w) : [w, ...list];
  await writeJSON(KEY_BOOKMARKS, next);
  return !exists; // new bookmarked state
}

export const StorageService = {
  getHistory,
  addToHistory,
  clearHistory,
  getBookmarks,
  isBookmarked,
  toggleBookmark,
};
export default StorageService;
