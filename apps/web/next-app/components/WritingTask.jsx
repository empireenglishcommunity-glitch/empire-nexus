'use client'
import { useState } from 'react'

export default function WritingTask() {
  const [text, setText] = useState('')
  const [feedback, setFeedback] = useState(null)
  const [loading, setLoading] = useState(false)

  const submitWriting = async () => {
    if (text.trim().length < 5) return
    setLoading(true)
    setFeedback(null)

    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, level: 'L0' }),
      })
      const data = await res.json()
      if (data.error) {
        setFeedback({ error: data.error })
      } else {
        setFeedback(data)
      }
    } catch (err) {
      setFeedback({ error: 'Connection error' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h4 className="font-arabic font-bold text-parchment mb-3">✍️ تمرين الكتابة</h4>
      <p className="font-arabic text-sm text-steel mb-4">
        اكتب ٣-٥ جمل بالإنجليزي عن نفسك. لا تستخدم مترجم — حاول بنفسك!
      </p>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full h-32 bg-sovereign-black border border-steel/20 rounded-sm p-4 text-parchment font-mono text-sm focus:border-imperial-gold/50 focus:outline-none resize-none"
        placeholder="Write in English here..."
        dir="ltr"
      />

      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-steel">{text.length} characters</span>
        <button
          onClick={submitWriting}
          disabled={loading || text.trim().length < 5}
          className={`px-6 py-2 font-arabic font-bold rounded-sm transition-colors ${
            loading ? 'bg-steel/20 text-steel cursor-wait' :
            text.trim().length < 5 ? 'bg-steel/10 text-steel/50 cursor-not-allowed' :
            'bg-imperial-gold text-sovereign-black hover:bg-imperial-gold/90'
          }`}
        >
          {loading ? '⏳ جارٍ التصحيح...' : 'أرسل للتصحيح ✨'}
        </button>
      </div>

      {/* AI Feedback Display */}
      {feedback && !feedback.error && (
        <div className="mt-6 border border-imperial-gold/20 rounded-sm bg-midnight-navy/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-arabic font-bold text-imperial-gold">📝 التصحيح</h4>
            <div className="flex items-center gap-2">
              <span className="font-heading text-xl text-imperial-gold">{feedback.score}</span>
              <span className="text-xs text-steel">/100</span>
              <span className="px-2 py-0.5 bg-imperial-gold/10 text-imperial-gold text-xs rounded-full">{feedback.rating}</span>
            </div>
          </div>

          {/* English feedback */}
          <p className="text-parchment/80 text-sm mb-4 leading-relaxed" dir="ltr">
            {feedback.feedback_en}
          </p>

          {/* Arabic summary */}
          <p className="font-arabic text-steel text-sm mb-4 p-3 bg-sovereign-black/50 rounded-sm">
            {feedback.feedback_ar}
          </p>

          {/* Corrections */}
          {feedback.corrections && feedback.corrections.length > 0 && (
            <div className="space-y-2 mb-4">
              <h5 className="font-arabic text-xs text-steel font-bold">التصحيحات:</h5>
              {feedback.corrections.map((c, i) => (
                <div key={i} className="flex items-start gap-2 text-sm p-2 bg-sovereign-black/30 rounded-sm" dir="ltr">
                  <span className="text-red-400 line-through">{c.wrong}</span>
                  <span className="text-imperial-gold">→</span>
                  <span className="text-emerald font-bold">{c.correct}</span>
                  {c.explanation && <span className="text-steel text-xs mr-2">({c.explanation})</span>}
                </div>
              ))}
            </div>
          )}

          {/* Focus area */}
          {feedback.one_focus && (
            <div className="p-3 border border-imperial-gold/10 rounded-sm">
              <p className="font-arabic text-xs text-imperial-gold mb-1">🎯 ركّز على هذا:</p>
              <p className="text-sm text-parchment/80" dir="ltr">{feedback.one_focus}</p>
            </div>
          )}
        </div>
      )}

      {/* Error display */}
      {feedback && feedback.error && (
        <div className="mt-4 p-3 border border-red-500/20 rounded-sm bg-red-500/5">
          <p className="font-arabic text-sm text-red-400">⚠️ {feedback.error}</p>
        </div>
      )}
    </div>
  )
}
