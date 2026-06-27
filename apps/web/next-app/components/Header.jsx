'use client'

export default function Header() {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-steel/10 bg-midnight-navy/50">
      <div>
        <h2 className="font-arabic text-xl font-bold text-parchment">المهام اليومية</h2>
        <p className="font-arabic text-sm text-steel">الخميس، الأسبوع الأول · المستوى صفر</p>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-left">
          <p className="font-arabic text-sm text-parchment">محمود</p>
          <p className="font-arabic text-xs text-imperial-gold">🌱 Recruit</p>
        </div>
        <div className="w-9 h-9 rounded-full bg-imperial-gold/20 flex items-center justify-center text-imperial-gold font-bold">
          م
        </div>
      </div>
    </header>
  )
}
