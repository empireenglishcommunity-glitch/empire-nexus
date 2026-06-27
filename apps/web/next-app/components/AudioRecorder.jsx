'use client'
import { useState, useRef } from 'react'

export default function AudioRecorder() {
  const [recording, setRecording] = useState(false)
  const [audioURL, setAudioURL] = useState(null)
  const [duration, setDuration] = useState(0)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setAudioURL(URL.createObjectURL(blob))
        stream.getTracks().forEach(track => track.stop())
      }

      mediaRecorder.start()
      setRecording(true)
      setDuration(0)
      timerRef.current = setInterval(() => setDuration(d => d + 1), 1000)
    } catch (err) {
      alert('يرجى السماح بالوصول للمايكروفون')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
      clearInterval(timerRef.current)
    }
  }

  const formatTime = (s) => `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`

  return (
    <div className="border border-steel/20 rounded-sm p-4 bg-sovereign-black/30">
      <div className="flex items-center gap-4">
        {/* Record button */}
        <button
          onClick={recording ? stopRecording : startRecording}
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${
            recording
              ? 'bg-red-600 animate-pulse shadow-[0_0_20px_rgba(220,38,38,0.4)]'
              : 'bg-imperial-gold/20 border-2 border-imperial-gold hover:bg-imperial-gold/30'
          }`}
        >
          {recording ? (
            <div className="w-5 h-5 bg-white rounded-sm" />
          ) : (
            <div className="w-5 h-5 bg-imperial-gold rounded-full" />
          )}
        </button>

        <div className="flex-1">
          {recording ? (
            <div>
              <p className="font-arabic text-sm text-red-400 font-bold">جارٍ التسجيل...</p>
              <p className="font-mono text-lg text-parchment">{formatTime(duration)}</p>
            </div>
          ) : audioURL ? (
            <div>
              <p className="font-arabic text-sm text-emerald font-bold">تم التسجيل ✅</p>
              <audio src={audioURL} controls className="mt-2 w-full h-8" />
            </div>
          ) : (
            <div>
              <p className="font-arabic text-sm text-steel">اضغط للتسجيل</p>
              <p className="font-arabic text-xs text-steel/60">سجّل الجملة المطلوبة بصوت واضح</p>
            </div>
          )}
        </div>

        {/* Re-record */}
        {audioURL && !recording && (
          <button
            onClick={() => { setAudioURL(null); setDuration(0) }}
            className="px-3 py-1 border border-steel/20 text-steel text-xs rounded-sm hover:border-imperial-gold/30 hover:text-imperial-gold transition-colors font-arabic"
          >
            أعد التسجيل
          </button>
        )}
      </div>

      {/* Submit */}
      {audioURL && (
        <button className="mt-4 w-full py-2 bg-imperial-gold/10 border border-imperial-gold/30 text-imperial-gold font-arabic font-bold rounded-sm hover:bg-imperial-gold/20 transition-colors">
          أرسل التسجيل 📤
        </button>
      )}
    </div>
  )
}
