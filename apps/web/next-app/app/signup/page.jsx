'use client'
import { useState } from 'react'
import { supabase } from '../../lib/supabase'

export default function Signup() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const handleSignup = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: name, level: 'L0', track: 'Core' } }
    })

    if (error) {
      setError(error.message)
    } else {
      setSuccess(true)
    }
    setLoading(false)
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="text-center max-w-sm">
          <div className="text-5xl mb-4">🏛️</div>
          <h2 className="font-arabic text-2xl font-bold text-imperial-gold mb-3">أهلاً بك في الإمبراطورية</h2>
          <p className="font-arabic text-steel mb-6">
            تم إنشاء حسابك. تحقق من بريدك الإلكتروني لتأكيد التسجيل.
          </p>
          <a href="/login" className="inline-block px-8 py-3 border border-imperial-gold/50 text-imperial-gold font-arabic font-bold rounded-sm hover:bg-imperial-gold/10 transition-colors">
            الدخول
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="font-heading text-2xl text-imperial-gold font-bold mb-2">Empire English</h1>
          <p className="font-arabic text-steel">ابنِ إمبراطوريتك — سجّل الآن</p>
        </div>

        <form onSubmit={handleSignup} className="space-y-4">
          <div>
            <label className="block font-arabic text-sm text-steel mb-1">الاسم</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3 bg-midnight-navy border border-steel/20 rounded-sm text-parchment focus:border-imperial-gold/50 focus:outline-none"
              placeholder="اسمك"
              required
            />
          </div>

          <div>
            <label className="block font-arabic text-sm text-steel mb-1">البريد الإلكتروني</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 bg-midnight-navy border border-steel/20 rounded-sm text-parchment focus:border-imperial-gold/50 focus:outline-none"
              placeholder="you@example.com"
              dir="ltr"
              required
            />
          </div>

          <div>
            <label className="block font-arabic text-sm text-steel mb-1">كلمة المرور</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-midnight-navy border border-steel/20 rounded-sm text-parchment focus:border-imperial-gold/50 focus:outline-none"
              placeholder="٦ أحرف على الأقل"
              dir="ltr"
              minLength={6}
              required
            />
          </div>

          {error && <p className="font-arabic text-sm text-red-400 text-center">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-imperial-gold text-sovereign-black font-arabic font-bold rounded-sm hover:bg-imperial-gold/90 transition-colors disabled:opacity-50"
          >
            {loading ? '⏳ جارٍ التسجيل...' : 'ابدأ رحلتك 🏛️'}
          </button>
        </form>

        <p className="text-center font-arabic text-sm text-steel mt-6">
          عندك حساب؟{' '}
          <a href="/login" className="text-imperial-gold hover:underline">دخول</a>
        </p>
      </div>
    </div>
  )
}
