"""Nutq 2 — self-hosted phoneme pronunciation scorer (engine core).

Pipeline (design §3):
  reference text --G2P--> expected phonemes
  audio          --allosaurus--> recognized phonemes
  align (Needleman-Wunsch, Arabic-substitution-aware) --> per-word + overall score

DESIGN NOTES
- Import-safe: importing this module does NOT load the model or heavy deps.
  The scoring MATH (g2p mapping, canon, alignment, scoring, feedback) is pure and
  unit-testable without torch/allosaurus. Model + audio decode are lazy.
- Free & offline: allosaurus + g2p_en run locally; no API, no per-use cost (R3).
- Beginner-kind but honest (R6): known Arabic-speaker substitutions get PARTIAL
  credit (not zero), but a genuinely wrong read still scores low (R2). Final
  fairness thresholds are CALIBRATED in Phase 3 on real Arabic-accented samples;
  Phase 1 ships sane defaults + a calibration hook.
"""
import logging
import os
import re
import shutil
import subprocess
import tempfile

logger = logging.getLogger("nutq-scorer")

# ── phoneme notation ────────────────────────────────────────────────────────
# g2p_en emits ARPAbet; map to IPA, then canonicalize so it aligns with the
# allosaurus (universal IPA) output on notation rather than acoustics.
ARPA2IPA = {
    'AA': 'ɑ', 'AE': 'æ', 'AH': 'ə', 'AO': 'ɔ', 'AW': 'aʊ', 'AY': 'aɪ', 'B': 'b',
    'CH': 'tʃ', 'D': 'd', 'DH': 'ð', 'EH': 'ɛ', 'ER': 'ɹ', 'EY': 'eɪ', 'F': 'f',
    'G': 'g', 'HH': 'h', 'IH': 'ɪ', 'IY': 'i', 'JH': 'dʒ', 'K': 'k', 'L': 'l',
    'M': 'm', 'N': 'n', 'NG': 'ŋ', 'OW': 'oʊ', 'OY': 'ɔɪ', 'P': 'p', 'R': 'ɹ',
    'S': 's', 'SH': 'ʃ', 'T': 't', 'TH': 'θ', 'UH': 'ʊ', 'UW': 'u', 'V': 'v',
    'W': 'w', 'Y': 'j', 'Z': 'z', 'ZH': 'ʒ',
}

# Collapse equivalent notations / near-equivalent vowels so the two phoneme
# sources compare fairly (does not merge contrasts that matter for a wrong read).
CANON = {
    'ɹ': 'r', 'ɡ': 'g', 'ɑ': 'a', 'ɐ': 'a', 'ʌ': 'a', 'ə': 'a', 'æ': 'a', 'ɜ': 'a',
    'ɚ': 'a', 'ɝ': 'a', 'ɛ': 'e', 'e': 'e', 'ɪ': 'i', 'i': 'i', 'ɨ': 'i', 'ʊ': 'u',
    'u': 'u', 'ʉ': 'u', 'ɔ': 'o', 'o': 'o', 'ɒ': 'o',
}

# Known Arabic-speaker English substitutions → PARTIAL credit (R6).
# Stored canonicalised + unordered.
_ARABIC_PAIRS = [
    ('p', 'b'), ('f', 'v'), ('v', 'w'), ('θ', 's'), ('θ', 't'),
    ('ð', 'd'), ('ð', 'z'), ('ŋ', 'n'), ('tʃ', 'ʃ'), ('dʒ', 'ʒ'),
]
ARABIC_SUB = {frozenset(p) for p in _ARABIC_PAIRS}

# Alignment costs
COST_SUB = 1.0        # unrelated substitution (a real error)
COST_PARTIAL = 0.4    # Arabic-substitution (credit 0.6)
COST_INDEL = 1.0      # insertion / deletion
_PARTIAL_QUALITY = 1.0 - COST_PARTIAL  # 0.6

MISSED_WORD_THRESHOLD = 0.5  # word quality below this → flagged "focus on"


def _canon_symbol(sym: str) -> list:
    """Strip diacritics/length/stress and expand multi-char into canon chars."""
    s = sym.strip().lower()
    for ch in ('ː', 'ˈ', 'ˌ', 'ʲ', 'ʰ', '̃', 'ʼ', '.', '̩', '̥', '̬', '̯'):
        s = s.replace(ch, '')
    out = []
    for c in s:
        if c:
            out.append(CANON.get(c, c))
    return out


def canon_seq(symbols) -> list:
    out = []
    for s in symbols:
        out.extend(_canon_symbol(s))
    return out


def _sub_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if frozenset((a, b)) in ARABIC_SUB:
        return COST_PARTIAL
    return COST_SUB


def align(ref: list, hyp: list):
    """Needleman-Wunsch alignment with Arabic-aware substitution cost.

    Returns (total_cost, insertions, per_ref_quality) where per_ref_quality[i]
    in [0,1] is how well reference phoneme i was produced (1 exact, 0.6 partial,
    0 wrong/deleted).
    """
    n, m = len(ref), len(hyp)
    # dp cost matrix + backpointer
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bp = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * COST_INDEL
        bp[i][0] = 'del'
    for j in range(1, m + 1):
        dp[0][j] = j * COST_INDEL
        bp[0][j] = 'ins'
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sc = dp[i - 1][j - 1] + _sub_cost(ref[i - 1], hyp[j - 1])
            dc = dp[i - 1][j] + COST_INDEL      # deletion (ref not matched)
            ic = dp[i][j - 1] + COST_INDEL      # insertion (extra hyp)
            best = min(sc, dc, ic)
            dp[i][j] = best
            bp[i][j] = 'sub' if best == sc else ('del' if best == dc else 'ins')

    # backtrack to get per-ref-position quality + count insertions
    quality = [0.0] * n
    insertions = 0
    i, j = n, m
    while i > 0 or j > 0:
        move = bp[i][j]
        if move == 'sub':
            c = _sub_cost(ref[i - 1], hyp[j - 1])
            quality[i - 1] = max(0.0, 1.0 - c)
            i -= 1
            j -= 1
        elif move == 'del':
            quality[i - 1] = 0.0
            i -= 1
        else:  # ins
            insertions += 1
            j -= 1
    return dp[n][m], insertions, quality


# ── calibration hook (Phase 3 tunes; Phase 1 = gentle identity) ──────────────
def calibrate(raw: float, level: str = "L0") -> float:
    """Map raw phoneme accuracy → student-facing 0-100.

    Phase 1 default is near-identity (honest). Phase 3 will fit anchor points on
    real Arabic-accented samples so a clean read lands high and a wrong read low.
    """
    return round(max(0.0, min(100.0, raw)), 1)


def ref_phonemes(text: str):
    """Reference text → (flat_syms, word_index_per_sym, words).

    Uses g2p_en (lazy import). Per-word G2P so we get clean word→phoneme spans
    for per-word scoring + 'focus on' words.
    """
    from g2p_en import G2p
    global _G2P
    try:
        g2p = _G2P
    except NameError:
        g2p = _G2P = G2p()

    words = re.findall(r"[A-Za-z']+", text)
    flat, word_idx, out_words = [], [], []
    for wi, w in enumerate(words):
        toks = g2p(w)
        syms = []
        for t in toks:
            base = re.sub(r'\d', '', str(t).strip())
            if base in ARPA2IPA:
                syms.extend(_canon_symbol(ARPA2IPA[base]))
        if not syms:
            continue
        out_words.append(w)
        for s in syms:
            flat.append(s)
            word_idx.append(len(out_words) - 1)
    return flat, word_idx, out_words


def score_from_phonemes(ref_flat, ref_word_idx, ref_words, hyp_flat, level="L0"):
    """Pure scoring math (no model) — the unit-tested core.

    Returns dict: score, raw_score, per_word[{word,accuracy}], missed_words.
    """
    if not ref_flat:
        return {"score": 0.0, "raw_score": 0.0, "per_word": [], "missed_words": []}

    _cost, insertions, quality = align(ref_flat, hyp_flat)
    earned = sum(quality)
    # small penalty for spurious extra sounds (guards against noise inflating)
    raw = max(0.0, earned - 0.5 * insertions) / len(ref_flat) * 100.0

    # per-word aggregation
    n_words = len(ref_words)
    wsum = [0.0] * n_words
    wcnt = [0] * n_words
    for q, wi in zip(quality, ref_word_idx):
        wsum[wi] += q
        wcnt[wi] += 1
    per_word, missed = [], []
    for wi, w in enumerate(ref_words):
        acc = (wsum[wi] / wcnt[wi]) if wcnt[wi] else 0.0
        per_word.append({"word": w, "accuracy": round(acc, 3)})
        if acc < MISSED_WORD_THRESHOLD:
            missed.append(w)
    return {
        "score": calibrate(raw, level),
        "raw_score": round(raw, 1),
        "per_word": per_word,
        "missed_words": missed[:5],
    }


def make_feedback(score: float, missed_words, level="L0"):
    """Basic bilingual template feedback (Phase 3 refines with sound-specific
    tips). Encouragement-first, not Nour-voiced (R8)."""
    if score >= 90:
        return ("Excellent! Your pronunciation is very clear.",
                "ممتاز! نطقك واضح جداً.")
    if score >= 70:
        if missed_words:
            w = missed_words[0]
            return (f"Great job! Very close. Practice the word '{w}' a few times slowly.",
                    f"أحسنت! قريب جداً. اتمرّن على كلمة '{w}' كذا مرة ببطء.")
        return ("Great job! Very natural. Keep practicing daily!",
                "أحسنت! صوتك طبيعي. استمر كل يوم!")
    if score >= 45:
        if missed_words:
            w = missed_words[0]
            return (f"Good effort! Focus on '{w}' — say it 5 times slowly, then speed up.",
                    f"مجهود كويس! ركّز على '{w}' — قولها ٥ مرات ببطء وبعدين بسرعة.")
        return ("Good effort! Listen to the model again and record once more.",
                "مجهود كويس! اسمع النموذج تاني وسجّل مرة كمان.")
    # low — honest but kind
    mw = (", ".join(missed_words[:3])) if missed_words else "the sounds"
    return (f"Nice try! Let's work on: {mw}. Listen to the model 3 times, then record again.",
            f"محاولة حلوة! نشتغل على: {mw}. اسمع النموذج ٣ مرات وسجّل تاني.")


# ── model + audio (lazy; not imported at module load) ────────────────────────
_RECOGNIZER = None


def _get_recognizer():
    global _RECOGNIZER
    if _RECOGNIZER is None:
        from allosaurus.app import read_recognizer
        _RECOGNIZER = read_recognizer()
    return _RECOGNIZER


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _to_wav(audio_bytes: bytes, filename: str = "rec.webm") -> str:
    src = tempfile.mktemp(suffix="_" + os.path.basename(filename or "rec.webm"))
    wav = tempfile.mktemp(suffix=".wav")
    with open(src, "wb") as f:
        f.write(audio_bytes)
    subprocess.run([_ffmpeg(), "-y", "-i", src, "-ar", "16000", "-ac", "1", wav],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    try:
        os.remove(src)
    except OSError:
        pass
    return wav


def recognize_phonemes(audio_bytes: bytes, filename: str = "rec.webm") -> list:
    wav = _to_wav(audio_bytes, filename)
    try:
        raw = _get_recognizer().recognize(wav)
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
    return canon_seq(raw.split())


def score_audio(audio_bytes: bytes, reference_text: str, level: str = "L0",
                filename: str = "rec.webm") -> dict:
    """Full pipeline: audio bytes + reference text → score result dict.

    Always returns a dict; on failure returns {ok: False, error: ...} so the
    caller can degrade gracefully (never crash the student flow).
    """
    try:
        ref_flat, ref_word_idx, ref_words = ref_phonemes(reference_text)
        if not ref_flat:
            return {"ok": False, "error": "no reference phonemes"}
        hyp_flat = recognize_phonemes(audio_bytes, filename)
        result = score_from_phonemes(ref_flat, ref_word_idx, ref_words, hyp_flat, level)
        fb_en, fb_ar = make_feedback(result["score"], result["missed_words"], level)
        result.update({
            "ok": True,
            "feedback_en": fb_en,
            "feedback_ar": fb_ar,
            "heard_phonemes": " ".join(hyp_flat),
            "expected": reference_text,
        })
        return result
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        logger.warning("score_audio failed: %s", e)
        return {"ok": False, "error": str(e)}
