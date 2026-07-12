"""Empire English Community Bot — AI Engine.

Handles all AI-powered content generation and evaluation using Gemini (primary)
with Groq as fallback. Provides:
  - Daily speaking mission generation
  - Writing evaluation and feedback
  - Vocabulary cheat sheet generation
  - Weekly progress summaries
  - Grammar pattern cards

All prompts are designed for Arabic-speaking learners at specific levels.
"""
import json
import logging
import aiohttp
from typing import Optional

from . import config

logger = logging.getLogger("empire-bot.ai")

# ============================================================
#  LLM API CALLS
# ============================================================

async def _call_gemini(prompt: str, temperature: float = 0.8) -> Optional[str]:
    """Call Google Gemini API. Returns raw text or None on failure."""
    if not config.GEMINI_API_KEY:
        return None
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning(f"Gemini API error: {resp.status}")
                    return None
                data = await resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return None


async def _call_groq(prompt: str, temperature: float = 0.8) -> Optional[str]:
    """Call Groq API (fallback). Returns raw text or None."""
    if not config.GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
    }
    payload = {
        "model": config.GROQ_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": "You are an expert English language tutor for Arabic speakers. Always return valid JSON when asked."},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning(f"Groq API error: {resp.status}")
                    return None
                data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return text.strip() if text else None
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        return None


async def _call_llm(prompt: str, temperature: float = 0.8) -> Optional[str]:
    """Call primary LLM (Gemini) with Groq fallback."""
    result = await _call_gemini(prompt, temperature)
    if result:
        return result
    logger.info("Gemini failed, trying Groq fallback...")
    return await _call_groq(prompt, temperature)


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response (handles code fences).

    Handles both a top-level object ({...}) and a top-level array
    ([...]) of objects -- generate_vocabulary_sheet()'s prompt
    explicitly asks the LLM to "return ONLY a valid JSON array", so an
    array response is a real, documented, expected shape here, not an
    edge case.

    Previously this searched for "{"/"}" unconditionally first, then
    only tried "["/"]" in an except block using the ALREADY-TRUNCATED
    text -- so for an array-of-objects response like
    '[{"word": "a"}, {"word": "b"}]', the "{"/"}" search would slice
    out `{"word": "a"}, {"word": "b"}` (first "{" to last "}"),
    stripping away the outer "["/"]" before the array fallback ever got
    a chance to see them, so parsing that (invalid, comma-joined,
    unbracketed) substring as JSON always failed and the whole
    function returned None for every array response.

    Fixed by finding both candidate substrings (object-delimited and
    array-delimited) against the ORIGINAL text, then trying whichever
    one starts earlier first (the true outermost wrapper), falling
    back to the other if that fails to parse.
    """
    if not text:
        return None
    t = text.strip()
    t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not t:
        return None

    obj_start, obj_end = t.find("{"), t.rfind("}")
    arr_start, arr_end = t.find("["), t.rfind("]")

    candidates = []
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidates.append((obj_start, t[obj_start:obj_end + 1]))
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        candidates.append((arr_start, t[arr_start:arr_end + 1]))

    # Try whichever delimiter starts earliest in the text first.
    candidates.sort(key=lambda c: c[0])
    for _, candidate_text in candidates:
        try:
            return json.loads(candidate_text)
        except json.JSONDecodeError:
            continue

    logger.warning(f"Failed to parse JSON from LLM response: {t[:200]}")
    return None


# ============================================================
#  SPEAKING MISSION GENERATOR
# ============================================================

async def generate_speaking_mission(level: str, week: int, day_name: str,
                                     mission_type: str, vocab_theme: str) -> Optional[dict]:
    """Generate a daily speaking mission for the given level/week/day.

    Returns dict with: mission_title, mission_title_ar, instructions_en,
    instructions_ar, guiding_questions, target_duration_seconds,
    target_phrases, phoneme_focus, example_response
    """
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])
    phoneme_info = config.PHONEME_WEEKS.get(week, config.PHONEME_WEEKS[1])

    prompt = f"""You are the AI engine for Empire English Community — a system-driven English learning program for Arabic speakers focused on American accent mastery.

Generate a Daily Speaking Mission for a Level {level} learner.

LEARNER CONTEXT:
- Level: {level} ({level_info['name']})
- Week: {week}
- Day: {day_name}
- Vocabulary theme: {vocab_theme}
- Mission type: {mission_type}
- Phoneme focus this week: {phoneme_info['focus']}
- Target speaking duration: {level_info['speaking_target_seconds']} seconds max

MISSION TYPES:
- self_introduction: Progressive self-intro (more detail each week)
- describe: Describe objects, routines, places
- list_count: Quantities, sequences, listing items
- read_aloud: Read provided text with phoneme focus
- answer_questions: Respond to 3 prompts
- shadow_repeat: Model sentence provided to repeat
- free_talk: Any topic, hit target duration

RULES:
- Use only vocabulary appropriate for week {week} of {level}
- Guiding questions must be simple enough for the learner's level
- Include Arabic translation of instructions for Level 0
- Target duration should be realistic for the level
- Example response should model what good output sounds like

Return ONLY valid JSON:
{{
  "mission_title": "short title in English",
  "mission_title_ar": "Arabic translation",
  "instructions_en": "2-3 sentence instructions",
  "instructions_ar": "Arabic instructions (for L0 learners)",
  "guiding_questions": ["question 1", "question 2", "question 3"],
  "target_duration_seconds": {level_info['speaking_target_seconds']},
  "target_phrases": ["phrase to try using", "another phrase"],
  "phoneme_focus": "today's pronunciation focus",
  "example_response": "2-3 sentence example of a good response"
}}"""

    result = await _call_llm(prompt, temperature=0.85)
    return _extract_json(result)


# ============================================================
#  WRITING EVALUATION
# ============================================================

async def evaluate_writing(submission: str, original_prompt: str,
                           level: str) -> Optional[dict]:
    """Evaluate a writing submission and return scores + feedback.

    Returns dict with: overall_score, grammar_score, vocabulary_score,
    organization_score, task_completion_score, feedback_en, feedback_ar,
    corrected_version, one_thing_to_practice, rating
    """
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])

    prompt = f"""You are a supportive English writing tutor for Empire English Community. The learner is an Arabic speaker at {level} ({level_info['name']}).

EVALUATE this writing submission:

SUBMISSION:
"{submission}"

TASK PROMPT:
"{original_prompt}"

LEVEL EXPECTATIONS:
- L0: simple sentences, SVO, present simple, 500-word vocabulary
- L1: paragraphs, past/future tense, 1500 words
- L2: essays, all tenses, conditionals, 3000 words
- L3: advanced style, near-native accuracy

SCORING RUBRIC (score each 0-100):
1. Grammar Accuracy (30%): sentence structure, verb forms, articles
2. Vocabulary (25%): appropriate word choice, variety
3. Organization (25%): logical order, coherence
4. Task Completion (20%): addressed prompt fully

FEEDBACK RULES:
- Be encouraging first, then constructive
- Maximum 3 corrections (don't overwhelm)
- For L0: focus ONLY on word order and verb form
- Show corrections: ~~wrong~~ → **correct**
- End with ONE specific thing to practice
- Keep feedback language simple for L0-L1

Return ONLY valid JSON:
{{
  "overall_score": 0-100,
  "grammar_score": 0-100,
  "vocabulary_score": 0-100,
  "organization_score": 0-100,
  "task_completion_score": 0-100,
  "feedback_en": "encouraging feedback with corrections",
  "feedback_ar": "Arabic summary for L0",
  "corrected_version": "full text with corrections applied",
  "one_thing_to_practice": "specific actionable focus",
  "rating": "Excellent/Strong/Satisfactory/Needs Work/Keep Trying"
}}"""

    result = await _call_llm(prompt, temperature=0.3)
    return _extract_json(result)


# ============================================================
#  VOCABULARY CHEAT SHEET
# ============================================================

async def generate_vocabulary_sheet(level: str, week: int,
                                     theme: str) -> Optional[list]:
    """Generate a weekly vocabulary set (8 words/day × 7 days = 56 words for L0).

    Returns list of word objects with: word, pronunciation, arabic,
    part_of_speech, example_sentence, common_mistake, collocation
    """
    level_info = config.LEVELS.get(level, config.LEVELS["L0"])
    words_per_day = 8 if level == "L0" else 10

    prompt = f"""Generate a vocabulary set for Empire English Community.

PARAMETERS:
- Level: {level} ({level_info['name']})
- Week: {week}
- Theme: {theme}
- Words needed: {words_per_day} words for today
- Learner's first language: Arabic

For each word provide:
1. word: the English word
2. pronunciation: simplified phonetic (not IPA — readable by beginners)
3. arabic: Arabic translation
4. part_of_speech: noun/verb/adjective/adverb/etc
5. example_sentence: using only words appropriate for this level
6. common_mistake: error Arabic speakers typically make
7. collocation: common word pair

REQUIREMENTS:
- Words from top frequency lists appropriate for {level}
- Mark words with sounds that don't exist in Arabic with ⚠️
- Order from concrete (nouns) to abstract (verbs, adjectives)

Return ONLY a valid JSON array of {words_per_day} word objects."""

    result = await _call_llm(prompt, temperature=0.7)
    parsed = _extract_json(result)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and "words" in parsed:
        return parsed["words"]
    return None


# ============================================================
#  GRAMMAR PATTERN CARD
# ============================================================

async def generate_grammar_card(level: str, week: int,
                                 pattern: str) -> Optional[dict]:
    """Generate a grammar pattern card.

    Returns dict with: pattern_name, pattern_name_ar, formula,
    when_to_use, examples, common_error, practice_sentences
    """
    prompt = f"""Generate a Grammar Pattern Card for Empire English Community.

Level: {level}, Week: {week}
Pattern to explain: {pattern}
Learner: Arabic speaker

The card should be:
- Simple and visual (formula-based, not rule-heavy)
- Include Arabic explanation for L0 learners
- Show the pattern as a formula: Subject + Verb + Object
- Give 5 clear examples
- Show the #1 common mistake Arabic speakers make
- Provide 3 practice sentences (fill-in-the-blank)

Return ONLY valid JSON:
{{
  "pattern_name": "English name",
  "pattern_name_ar": "Arabic name",
  "formula": "Subject + verb-s + object (for he/she/it)",
  "when_to_use": "1-2 sentence explanation",
  "when_to_use_ar": "Arabic explanation",
  "examples": ["example 1", "example 2", "example 3", "example 4", "example 5"],
  "common_error": "description of typical Arabic speaker mistake",
  "common_error_correct": "the correct form",
  "practice_sentences": ["I ___ (go) to work.", "She ___ (like) coffee.", "They ___ (have) a car."]
}}"""

    result = await _call_llm(prompt, temperature=0.5)
    return _extract_json(result)


# ============================================================
#  WEEKLY PROGRESS SUMMARY
# ============================================================

async def generate_progress_summary(member_name: str, level: str,
                                     week: int, stats: dict) -> Optional[str]:
    """Generate a personalized weekly progress summary message.

    stats should contain: tasks_completed, total_tasks, streak,
    speaking_score, writing_score, strongest_area, weakest_area
    """
    prompt = f"""Generate a weekly progress summary for an Empire English Community member.

MEMBER: {member_name}
LEVEL: {level}
WEEK: {week}

STATS THIS WEEK:
- Tasks completed: {stats.get('tasks_completed', 0)} / {stats.get('total_tasks', 49)}
- Current streak: {stats.get('streak', 0)} days
- Speaking score: {stats.get('speaking_score', 'N/A')}
- Writing score: {stats.get('writing_score', 'N/A')}
- Strongest area: {stats.get('strongest_area', 'N/A')}
- Weakest area: {stats.get('weakest_area', 'N/A')}

TONE: Supportive, encouraging, honest. Like a coach who believes in them.
LANGUAGE: English (simple for L0-L1).
LENGTH: 4-6 sentences maximum.

Include:
1. One specific win to celebrate
2. One area to focus on next week
3. An encouraging closing line

Return the message as plain text (not JSON). No markdown headers."""

    return await _call_llm(prompt, temperature=0.8)


# ============================================================
#  DAILY TASK FEEDBACK (quick motivational response)
# ============================================================

async def quick_feedback(member_name: str, task_type: str,
                         feeling: int = 5) -> str:
    """Generate a short motivational response after task submission.

    feeling: 1-10 (how the learner felt about the task)
    Returns a 1-2 sentence motivational message.
    """
    prompt = f"""You are Empire English Bot. A learner named {member_name} just completed their {task_type} task and rated their feeling as {feeling}/10.

Write a SHORT motivational response (1-2 sentences max). Be specific to the task type:
- accent: comment on pronunciation practice
- vocab: comment on word learning
- shadow: comment on shadowing practice
- speaking: celebrate speaking courage
- listening: comment on ear training
- writing: celebrate putting words on paper
- community: celebrate participation

If feeling < 5: be extra supportive ("tough days build strength")
If feeling >= 7: celebrate their energy
Keep it warm but brief. Arabic speakers. No emojis overload (max 1)."""

    result = await _call_llm(prompt, temperature=0.9)
    if result and len(result) < 300:
        return result
    # Fallback messages if AI fails
    fallbacks = {
        "accent": "Great work on your pronunciation practice! Every rep builds the habit. 🎯",
        "vocab": "Words learned today are investments in tomorrow's conversations.",
        "shadow": "Shadowing is where fluency lives. Your brain is rewiring right now.",
        "speaking": "You spoke today. That's braver than most people ever get. Keep going.",
        "listening": "Your ears are getting sharper. Trust the process.",
        "writing": "Putting words on paper is how thoughts become fluency.",
        "community": "Showing up for others shows up for yourself. Well done.",
    }
    return fallbacks.get(task_type, "Task completed. One step closer. Keep building. 🏛️")


# ============================================================
#  ACCENT DRILL GENERATOR
# ============================================================

async def generate_accent_drill(level: str, week: int) -> Optional[dict]:
    """Generate today's accent/phoneme drill based on the week's focus.

    Returns dict with: phonemes, minimal_pairs, words, sentences,
    instructions_en, instructions_ar
    """
    phoneme_info = config.PHONEME_WEEKS.get(week, config.PHONEME_WEEKS[1])

    prompt = f"""Generate an accent drill for Empire English Community.

Level: {level}, Week: {week}
Today's phoneme focus: {phoneme_info['focus']}
Vowels this week: {', '.join(phoneme_info['vowels'])}
Consonants this week: {', '.join(phoneme_info['consonants'])}

Create a 10-minute drill with:
1. phonemes: list of 2-3 target sounds for today
2. minimal_pairs: 4 pairs of words that differ by one sound
3. words: 6 practice words containing the target sounds
4. sentences: 2 sentences loaded with the target sounds
5. instructions_en: brief drill instructions (English)
6. instructions_ar: Arabic translation of instructions

Focus on sounds that DON'T EXIST in Arabic (p/b, v/f, θ/ð, vowel length).

Return ONLY valid JSON:
{{
  "phonemes": ["/θ/", "/ð/"],
  "minimal_pairs": [["think", "sink"], ["three", "tree"], ["bath", "bass"], ["this", "dis"]],
  "words": ["think", "three", "thank", "the", "this", "that"],
  "sentences": ["I think this is the third thing.", "They thought about three things."],
  "instructions_en": "Listen to each pair. Say both. Record the sentences.",
  "instructions_ar": "استمع لكل زوج. انطق الاثنين. سجّل الجُمل."
}}"""

    result = await _call_llm(prompt, temperature=0.6)
    return _extract_json(result)
