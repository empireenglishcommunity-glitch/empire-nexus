const GEMINI_API_KEY = process.env.GEMINI_API_KEY || ''
const GEMINI_MODEL = 'gemini-2.5-flash-lite'

export async function evaluateWriting(text, level = 'L0') {
  if (!GEMINI_API_KEY) return { error: 'AI not configured' }

  const prompt = `You are a supportive English writing tutor for Arabic speakers at Level ${level} (absolute beginner).

EVALUATE this writing:
"${text}"

RULES:
- Be encouraging first, then constructive
- Maximum 3 corrections (don't overwhelm)
- For Level 0: focus ONLY on word order and verb form
- Show corrections as: wrong → correct
- End with ONE thing to practice
- Keep feedback in simple English + Arabic summary

Return ONLY valid JSON:
{
  "score": 0-100,
  "rating": "Excellent/Strong/Satisfactory/Needs Work/Keep Trying",
  "feedback_en": "Your encouraging feedback with corrections here",
  "feedback_ar": "ملخص بالعربي هنا",
  "corrections": [{"wrong": "...", "correct": "...", "explanation": "..."}],
  "one_focus": "One specific thing to practice this week"
}`

  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.3 },
        }),
      }
    )

    if (!res.ok) return { error: `AI error: ${res.status}` }

    const data = await res.json()
    const raw = data?.candidates?.[0]?.content?.parts?.[0]?.text || ''

    // Extract JSON from response
    let cleaned = raw.trim()
      .replace(/^```json\s*/i, '')
      .replace(/^```\s*/, '')
      .replace(/```\s*$/, '')

    const start = cleaned.indexOf('{')
    const end = cleaned.lastIndexOf('}')
    if (start !== -1 && end > start) {
      cleaned = cleaned.slice(start, end + 1)
    }

    return JSON.parse(cleaned)
  } catch (err) {
    return { error: `Parse error: ${err.message}` }
  }
}
