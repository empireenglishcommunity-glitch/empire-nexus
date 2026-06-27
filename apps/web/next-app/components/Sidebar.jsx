'use client'
import { useState } from 'react'

const nav = [
  { id: 'today', icon: '📋', label: 'المهام اليومية', labelEn: 'Daily Duty' },
  { id: 'progress', icon: '📊', label: 'تقدّمي', labelEn: 'Progress' },
  { id: 'accent', icon: '🎯', label: 'معمل النطق', labelEn: 'Accent Lab' },
  { id: 'lessons', icon: '📚', label: 'الدروس', labelEn: 'Lessons' },
  { id: 'community', icon: '💬', label: 'المجتمع', labelEn: 'Community' },
]

export default function Sidebar() {
  const [active, setActive] = useState('today')

  return (
    <aside className="hidden md:flex flex-col w-64 bg-midnight-navy border-l border-steel/10 p-4">
      {/* Logo */}
      <div className="mb-8 px-3">
        <h1 className="font-heading text-imperial-gold text-lg font-bold">Empire English</h1>
        <p className="font-arabic text-xs text-steel mt-1">نظام التعلّم اليومي</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1">
        {nav.map(item => (
          <button
            key={item.id}
            onClick={() => setActive(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-3 rounded-sm text-right transition-colors ${
              active === item.id
                ? 'bg-imperial-gold/10 text-imperial-gold border-r-2 border-imperial-gold'
                : 'text-steel hover:text-parchment hover:bg-steel/5'
            }`}
          >
            <span className="text-lg">{item.icon}</span>
            <span className="font-arabic text-sm">{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Streak widget */}
      <div className="mt-auto p-4 border border-imperial-gold/20 rounded-sm bg-sovereign-black/50">
        <div className="flex items-center justify-between">
          <span className="font-arabic text-xs text-steel">سلسلتك</span>
          <span className="text-imperial-gold font-bold text-lg">🔥 14</span>
        </div>
        <div className="mt-2 h-1.5 bg-steel/10 rounded-full overflow-hidden">
          <div className="h-full bg-imperial-gold rounded-full" style={{width: '57%'}} />
        </div>
        <p className="font-arabic text-xs text-steel mt-1">4/7 مهام اليوم</p>
      </div>
    </aside>
  )
}
