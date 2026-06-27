'use client'
import { useState } from 'react'
import { supabase } from '../../lib/supabase'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    const { error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError(error.message === 'Invalid login credentials'
        ? 'البريد أو كلمة المرور غير صحيحة'
        : error.message)
    } else {
      window.location.href = '/'
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="font-heading text-2xl text-imperial-gold font-bold mb-2">Empire English</h1>
          <p className="font-arabic text-steel">ادخل إلى إمبراطوريتك</p>
        </div>

        {/* Login form */}
        <form onSubmit={handleLogin} className="space-y-4">
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
              placeholder="••••••••"
              dir="ltr"
              required
            />
          </div>

          {error && (
            <p className="font-arabic text-sm text-red-400 text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-imperial-gold text-sovereign-black font-arabic font-bold rounded-sm hover:bg-imperial-gold/90 transition-colors disabled:opacity-50"
          >
            {loading ? '⏳ جارٍ الدخول...' : 'دخول'}
          </button>
        </form>

        {/* Sign up link */}
        <p className="text-center font-arabic text-sm text-steel mt-6">
          ما عندك حساب؟{' '}
          <a href="/signup" className="text-imperial-gold hover:underline">سجّل الآن</a>
        </p>
      </div>
    </div>
  )
}
