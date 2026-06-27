'use client'
import { useState } from 'react'
import AudioRecorder from './AudioRecorder'

const tasks = [
  { id: 'accent', emoji: '🎯', name: 'تدريب النطق', nameEn: 'Accent Drill', time: '10 د', instructions: 'أصوات اليوم: /p/ و /b/ — تمرّن على الفرق بينهم. سجّل نفسك.', status: 'current' },
  { id: 'vocab', emoji: '📖', name: 'مفردات', nameEn: 'Vocabulary', time: '10 د', instructions: 'تعلّم ٨ كلمات جديدة من موضوع "التحيات والتعريف بالنفس".', status: 'locked' },
  { id: 'shadow', emoji: '🎧', name: 'محاكاة', nameEn: 'Shadowing', time: '10 د', instructions: 'استمع وكرّر. قلّد الإيقاع والنطق.', status: 'locked' },
  { id: 'speaking', emoji: '🎙️', name: 'مهمة كلام', nameEn: 'Speaking', time: '10 د', instructions: 'سجّل ٣٠ ثانية: عرّف عن نفسك بالإنجليزي.', status: 'locked' },
  { id: 'listening', emoji: '👂', name: 'استماع', nameEn: 'Listening', time: '8 د', instructions: 'استمع للمقطع وأجب على ٣ أسئلة.', status: 'locked' },
  { id: 'writing', emoji: '✍️', name: 'كتابة', nameEn: 'Writing', time: '7 د', instructions: 'اكتب ٣ جمل عن نفسك. الذكاء الاصطناعي يصحّح.', status: 'locked' },
  { id: 'community', emoji: '💬', name: 'مجتمع', nameEn: 'Community', time: '5+ د', instructions: 'ادخل Voice Lounge أو رد على أحد في المجتمع.', status: 'locked' },
]

export default function DailyTasks() {
  const [completed, setCompleted] = useState([])
  const [activeTask, setActiveTask] = useState('accent')

  const currentTask = tasks.find(t => t.id === activeTask)
  const completedCount = completed.length

  return (
    <div className="max-w-4xl mx-auto">
      {/* Progress bar */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <span className="font-arabic text-sm text-steel">تقدّم اليوم</span>
          <span className="font-arabic text-sm text-imperial-gold font-bold">{completedCount}/7</span>
        </div>
        <div className="flex gap-1">
          {tasks.map((t, i) => (
            <div
              key={t.id}
              className={`flex-1 h-2 rounded-full transition-colors ${
                completed.includes(t.id) ? 'bg-imperial-gold' :
                t.id === activeTask ? 'bg-imperial-gold/40' :
                'bg-steel/10'
              }`}
            />
          ))}
        </div>
      </div>

      {/* Current task card */}
      <div className="border border-imperial-gold/30 rounded-sm bg-midnight-navy/50 p-8 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-3xl">{currentTask.emoji}</span>
          <div>
            <h3 className="font-arabic text-xl font-bold text-parchment">{currentTask.name}</h3>
            <p className="text-sm text-steel">{currentTask.nameEn} · {currentTask.time}</p>
          </div>
          <span className="mr-auto px-3 py-1 bg-imperial-gold/10 text-imperial-gold text-xs rounded-full font-arabic">
            {tasks.findIndex(t => t.id === activeTask) + 1}/7
          </span>
        </div>

        <p className="font-arabic text-lg text-parchment/80 mb-6 leading-relaxed">
          {currentTask.instructions}
        </p>

        {/* Task-specific content area */}
        <div className="bg-sovereign-black/50 border border-steel/10 rounded-sm p-6 mb-6">
          {activeTask === 'accent' && (
            <div>
              <h4 className="font-arabic font-bold text-parchment mb-3">تدريب أصوات /p/ و /b/</h4>
              <p className="font-arabic text-steel text-sm mb-4">
                /p/ = الشفاه مغلقة → هواء بدون صوت (حط يدك قدام فمك — تحس بالهواء)
                <br/>
                /b/ = الشفاه مغلقة → هواء + اهتزاز (حط يدك على حلقك — تحس بالاهتزاز)
              </p>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[['pat','bat'],['pin','bin'],['park','bark'],['pig','big']].map(([a,b], i) => (
                  <div key={i} className="flex items-center justify-center gap-4 p-3 bg-midnight-navy rounded-sm">
                    <span className="text-parchment font-mono">{a}</span>
                    <span className="text-imperial-gold">↔</span>
                    <span className="text-parchment font-mono">{b}</span>
                  </div>
                ))}
              </div>
              <p className="font-arabic text-sm text-imperial-gold mb-4">🎙️ سجّل نفسك تقول: "Pat put the pen in the paper bag."</p>
              <AudioRecorder />
            </div>
          )}

          {activeTask === 'writing' && (
            <div>
              <h4 className="font-arabic font-bold text-parchment mb-3">اكتب ٣ جمل عن نفسك</h4>
              <textarea
                className="w-full h-32 bg-sovereign-black border border-steel/20 rounded-sm p-4 text-parchment font-mono text-sm focus:border-imperial-gold/50 focus:outline-none resize-none"
                placeholder="Write here... اكتب هنا"
                dir="ltr"
              />
              <button className="mt-3 px-6 py-2 bg-imperial-gold text-sovereign-black font-arabic font-bold rounded-sm hover:bg-imperial-gold/90 transition-colors">
                أرسل للتصحيح ✨
              </button>
            </div>
          )}

          {activeTask !== 'accent' && activeTask !== 'writing' && (
            <p className="font-arabic text-steel text-center py-8">محتوى المهمة سيظهر هنا...</p>
          )}
        </div>

        {/* Complete button */}
        <button
          onClick={() => {
            if (!completed.includes(activeTask)) {
              setCompleted([...completed, activeTask])
            }
            const currentIndex = tasks.findIndex(t => t.id === activeTask)
            if (currentIndex < tasks.length - 1) {
              setActiveTask(tasks[currentIndex + 1].id)
            }
          }}
          className="w-full py-4 bg-imperial-gold text-sovereign-black font-arabic font-bold text-lg rounded-sm hover:bg-imperial-gold/90 transition-colors"
        >
          {completed.includes(activeTask) ? 'تم ✅ — انتقل للتالي' : 'أكملت هذه المهمة ✅'}
        </button>
      </div>

      {/* Task list (collapsed) */}
      <div className="space-y-2">
        {tasks.map((task, i) => (
          <button
            key={task.id}
            onClick={() => setActiveTask(task.id)}
            className={`w-full flex items-center gap-3 p-3 rounded-sm transition-colors ${
              task.id === activeTask ? 'border border-imperial-gold/30 bg-midnight-navy/50' :
              completed.includes(task.id) ? 'bg-emerald/5 border border-emerald/20' :
              'border border-steel/5 hover:border-steel/20'
            }`}
          >
            <span className="text-lg">{task.emoji}</span>
            <span className="font-arabic text-sm flex-1 text-right">{task.name}</span>
            <span className="text-xs text-steel">{task.time}</span>
            {completed.includes(task.id) && <span className="text-emerald">✅</span>}
          </button>
        ))}
      </div>
    </div>
  )
}
