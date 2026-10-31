import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import BoardCanvas from '../components/BoardCanvas.jsx'
import CheckpointModal from '../components/CheckpointModal.jsx'
import Header from '../components/Header.jsx'

const SUBJECTS = ['general', 'math', 'physics', 'chemistry', 'electronics', 'ai']
const LEVELS = ['beginner', 'intermediate', 'advanced']
const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi' },
  { code: 'kn', label: 'Kannada' },
]

export default function Studio() {
  const [tab, setTab] = useState('create')
  const [form, setForm] = useState({
    topic: '',
    subject: 'physics',
    difficulty: 'beginner',
    steps: 5,
    language: 'en',
    tts: false,
  })
  const [job, setJob] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [checkpoint, setCheckpoint] = useState(null)
  const [error, setError] = useState(null)
  const [library, setLibrary] = useState([])
  const [busy, setBusy] = useState(false)

  const refreshLibrary = useCallback(async () => {
    try {
      const data = await api.library()
      setLibrary(data.lessons || [])
    } catch {
      /* library optional */
    }
  }, [])

  useEffect(() => {
    refreshLibrary()
  }, [refreshLibrary])

  const pollJob = useCallback(async (id) => {
    for (let i = 0; i < 600; i++) {
      await new Promise((r) => setTimeout(r, 1000))
      try {
        const st = await api.session(id)
        setJob(st)
        if (st.state === 'ready') {
          setSessionId(id)
          setPlaying(false)
          setBusy(false)
          return
        }
        if (st.state === 'error') {
          setError(st.error || 'Generation failed')
          setBusy(false)
          return
        }
      } catch (err) {
        setError(String(err.message || err))
        setBusy(false)
        return
      }
    }
    setError('Timed out waiting for the lesson')
    setBusy(false)
  }, [])

  const generate = async (e) => {
    e.preventDefault()
    if (!form.topic.trim()) return
    setError(null)
    setJob(null)
    setPlaying(false)
    setBusy(true)
    setCheckpoint(null)
    try {
      const st = await api.generate({ ...form, topic: form.topic.trim(), use_rag: false, use_rerank: false })
      setSessionId(st.session_id)
      setJob(st)
      pollJob(st.session_id)
    } catch (err) {
      setError(String(err.message || err))
      setBusy(false)
    }
  }

  const openSample = async () => {
    setError(null)
    setJob(null)
    setPlaying(false)
    setBusy(true)
    setCheckpoint(null)
    try {
      const st = await api.open({ tts: false })
      setSessionId(st.session_id)
      setJob(st)
      pollJob(st.session_id)
    } catch (err) {
      setError(String(err.message || err))
      setBusy(false)
    }
  }

  const openLesson = async (path) => {
    setError(null)
    setJob(null)
    setPlaying(false)
    setBusy(true)
    setCheckpoint(null)
    try {
      const st = await api.open({ path, tts: false })
      setSessionId(st.session_id)
      setJob(st)
      pollJob(st.session_id)
    } catch (err) {
      setError(String(err.message || err))
      setBusy(false)
    }
  }

  const onTime = useCallback((t, isPlaying) => {
    setPlaying(isPlaying)
  }, [])

  const onCheckpoint = useCallback((cp) => {
    setCheckpoint(cp)
  }, [])

  const continueLesson = async () => {
    const cp = checkpoint
    setCheckpoint(null)
    if (sessionId) {
      try {
        await api.resetCheckpoints(sessionId)
        if (cp) {
          await api.seek(sessionId, cp.at_ms + 100)
        }
      } catch {
        /* ignore */
      }
    }
    setPlaying(true)
  }

  const togglePlay = () => {
    if (!sessionId) return
    if (checkpoint) return
    setPlaying((p) => !p)
  }

  const stop = () => {
    setPlaying(false)
    if (sessionId) {
      api.seek(sessionId, 0).catch(() => {})
    }
  }

  const progressLines = job?.progress || []
  const ready = job?.state === 'ready'

  return (
    <div className="min-h-screen bg-black text-white">
      <Header />
      <main className="gutter-x pt-[calc(var(--header-height)+1.5rem)] pb-10">
        <div className="grid gap-8 lg:grid-cols-[380px_1fr] xl:grid-cols-[420px_1fr]">
          <aside className="flex flex-col gap-6">
            <div className="flex gap-1 border-b border-[#222]">
              {['create', 'library'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={`px-4 py-3 text-sm capitalize transition-colors ${
                    tab === t ? 'border-b-2 border-[#ff3700] text-white' : 'text-white/45 hover:text-white/80'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>

            {tab === 'create' && (
              <form onSubmit={generate} className="flex flex-col gap-4">
                <label className="block">
                  <span className="text-eyebrow">Topic</span>
                  <input
                    value={form.topic}
                    onChange={(e) => setForm({ ...form, topic: e.target.value })}
                    placeholder="Newton's second law"
                    className="mt-2 w-full border border-[#333] bg-transparent px-4 py-3 text-sm outline-none focus:border-white/60"
                    maxLength={200}
                  />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="text-eyebrow">Subject</span>
                    <select
                      value={form.subject}
                      onChange={(e) => setForm({ ...form, subject: e.target.value })}
                      className="mt-2 w-full border border-[#333] bg-black px-3 py-3 text-sm outline-none focus:border-white/60"
                    >
                      {SUBJECTS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-eyebrow">Level</span>
                    <select
                      value={form.difficulty}
                      onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
                      className="mt-2 w-full border border-[#333] bg-black px-3 py-3 text-sm outline-none focus:border-white/60"
                    >
                      {LEVELS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-eyebrow">Language</span>
                    <select
                      value={form.language}
                      onChange={(e) => setForm({ ...form, language: e.target.value })}
                      className="mt-2 w-full border border-[#333] bg-black px-3 py-3 text-sm outline-none focus:border-white/60"
                    >
                      {LANGS.map((l) => (
                        <option key={l.code} value={l.code}>
                          {l.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-eyebrow">Steps</span>
                    <input
                      type="number"
                      min={1}
                      max={8}
                      value={form.steps}
                      onChange={(e) => setForm({ ...form, steps: Number(e.target.value) })}
                      className="mt-2 w-full border border-[#333] bg-black px-3 py-3 text-sm outline-none focus:border-white/60"
                    />
                  </label>
                </div>
                <label className="flex items-center gap-3 text-sm text-white/70">
                  <input
                    type="checkbox"
                    checked={form.tts}
                    onChange={(e) => setForm({ ...form, tts: e.target.checked })}
                    className="h-4 w-4 accent-[#ff3700]"
                  />
                  Narrate with TTS (slower)
                </label>
                <div className="flex gap-3">
                  <button type="submit" className="btn-primary flex-1 justify-center" disabled={busy}>
                    {busy ? 'Working…' : 'Generate lesson'}
                  </button>
                  <button type="button" className="btn-ghost" onClick={openSample} disabled={busy}>
                    Open sample
                  </button>
                </div>
                {error && (
                  <p className="border border-[#522] bg-[#1a0808] px-4 py-3 text-sm text-red-300">{error}</p>
                )}
                {progressLines.length > 0 && (
                  <div className="border border-[#222] p-4 text-xs text-white/50 max-h-32 overflow-y-auto">
                    {progressLines.slice(-6).map((line, i) => (
                      <div key={i}>· {line}</div>
                    ))}
                  </div>
                )}
                {ready && job && (
                  <div className="border border-[#222] p-4 text-sm">
                    <div className="font-medium">{job.title}</div>
                    <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-white/50">
                      <span>Subject: {job.subject}</span>
                      <span>Language: {job.language}</span>
                      <span>Steps: {job.steps}</span>
                      <span>Actions: {job.actions}</span>
                      <span>Score: {job.score}/100</span>
                      <span>Duration: {Math.round((job.duration_ms || 0) / 1000)}s</span>
                    </div>
                    {job.warnings?.length > 0 && (
                      <ul className="mt-3 text-xs text-amber-200/70">
                        {job.warnings.map((w, i) => (
                          <li key={i}>⚠ {w}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </form>
            )}

            {tab === 'library' && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <span className="text-eyebrow">{library.length} lessons</span>
                  <button type="button" className="text-xs text-white/50 link-underline" onClick={refreshLibrary}>
                    Refresh
                  </button>
                </div>
                {library.length === 0 && (
                  <p className="text-sm text-white/40">No lessons yet. Generate one to fill the library.</p>
                )}
                {library.map((lesson) => (
                  <button
                    key={lesson.lesson_id}
                    type="button"
                    onClick={() => openLesson(lesson.path)}
                    className="border border-[#222] p-4 text-left transition-colors hover:border-white/40"
                  >
                    <div className="font-medium">{lesson.title}</div>
                    <div className="mt-1 text-xs text-white/45">
                      {lesson.subject} · {lesson.language} · {lesson.steps} steps · {lesson.score}/100
                      {lesson.favorite ? ' · ★' : ''}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </aside>

          <section className="flex min-h-[70vh] flex-col">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-h3">Blackboard</h1>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-ghost !py-2 !px-5 text-sm"
                  onClick={togglePlay}
                  disabled={!sessionId || !!checkpoint}
                >
                  {playing ? 'Pause' : 'Play'}
                </button>
                <button type="button" className="btn-ghost !py-2 !px-5 text-sm" onClick={stop} disabled={!sessionId}>
                  Stop
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1">
              <BoardCanvas
                sessionId={sessionId}
                playing={playing && !checkpoint}
                onTime={onTime}
                onCheckpoint={onCheckpoint}
                onError={setError}
              />
            </div>
            {job?.tts_error && (
              <p className="mt-3 text-xs text-amber-200/70">TTS note: {job.tts_error}</p>
            )}
            <p className="mt-4 text-xs text-white/30">
              Generation needs a local Ollama server. The sample lesson works locally.{' '}
              <Link to="/" className="link-underline">
                Back to home
              </Link>
            </p>
          </section>
        </div>
      </main>

      <CheckpointModal checkpoint={checkpoint} onContinue={continueLesson} />
    </div>
  )
}
