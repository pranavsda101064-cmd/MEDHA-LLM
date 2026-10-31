import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const BOARD_BG = '#0e1a13'

export default function BoardCanvas({ sessionId, playing, onTime, onCheckpoint, onError }) {
  const canvasRef = useRef(null)
  const wrapRef = useRef(null)
  const timeRef = useRef(0)
  const playingRef = useRef(false)
  const lastFrameRef = useRef(0)
  const checkpointAtRef = useRef(0)
  const [duration, setDuration] = useState(0)
  const [position, setPosition] = useState(0)
  const strokesRef = useRef([])
  const firedCheckpointsRef = useRef(new Set())
  const lastFetchRef = useRef(0)
  const rafRef = useRef(0)

  useEffect(() => {
    const wasPlaying = playingRef.current
    playingRef.current = playing
    if (playing && !wasPlaying) {
      lastFrameRef.current = 0
    }
  }, [playing])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const w = wrap.clientWidth
    const h = wrap.clientHeight
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
    }
    const ctx = canvas.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.fillStyle = BOARD_BG
    ctx.fillRect(0, 0, w, h)

    ctx.strokeStyle = 'rgba(255,255,255,0.04)'
    ctx.lineWidth = 1
    for (let x = 0; x < w; x += 48) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, h)
      ctx.stroke()
    }
    for (let y = 0; y < h; y += 48) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(w, y)
      ctx.stroke()
    }

    const strokes = strokesRef.current
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    for (const s of strokes) {
      const pts = s.points
      if (!pts || pts.length < 2) continue
      const count = Math.max(2, Math.floor(pts.length * (s.progress ?? 1)))
      ctx.strokeStyle = s.color
      ctx.globalAlpha = s.alpha ?? 1
      ctx.lineWidth = (s.width || 3) * (Math.min(w, h) / 720)
      ctx.beginPath()
      ctx.moveTo(pts[0][0] * w, pts[0][1] * h)
      for (let i = 1; i < count; i++) {
        ctx.lineTo(pts[i][0] * w, pts[i][1] * h)
      }
      ctx.stroke()
    }
    ctx.globalAlpha = 1
  }, [])

  const tickRef = useRef(null)
  tickRef.current = (now) => {
    rafRef.current = requestAnimationFrame((t) => tickRef.current?.(t))
    const last = lastFrameRef.current || now
    const dt = now - last
    lastFrameRef.current = now

    if (playingRef.current && duration > 0) {
      timeRef.current = Math.min(duration, timeRef.current + dt)
      if (timeRef.current >= duration) {
        playingRef.current = false
        onTime?.(timeRef.current, false)
      } else {
        onTime?.(timeRef.current, true)
      }
      setPosition(timeRef.current)

      if (timeRef.current - checkpointAtRef.current > 400) {
        checkpointAtRef.current = timeRef.current
        api
          .checkpoint(sessionId, timeRef.current)
          .then((cp) => {
            if (cp && !firedCheckpointsRef.current.has(cp.step_id)) {
              firedCheckpointsRef.current.add(cp.step_id)
              playingRef.current = false
              onTime?.(timeRef.current, false)
              onCheckpoint?.(cp)
            }
          })
          .catch(() => {})
      }

      if (timeRef.current - lastFetchRef.current > 90) {
        lastFetchRef.current = timeRef.current
        api
          .frame(sessionId, timeRef.current)
          .then((f) => {
            strokesRef.current = f.strokes
            draw()
          })
          .catch((err) => onError?.(String(err.message || err)))
      }
    }
  }

  useEffect(() => {
    lastFrameRef.current = 0
    const id = requestAnimationFrame((t) => tickRef.current?.(t))
    rafRef.current = id
    return () => cancelAnimationFrame(rafRef.current)
  }, [])

  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    firedCheckpointsRef.current = new Set()
    const load = async () => {
      try {
        const f = await api.frame(sessionId, 0)
        if (cancelled) return
        strokesRef.current = f.strokes
        draw()
        const st = await api.session(sessionId)
        if (cancelled) return
        setDuration(st.duration_ms || 0)
        timeRef.current = 0
        setPosition(0)
      } catch (err) {
        if (!cancelled) onError?.(String(err.message || err))
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [sessionId, draw, onError])

  const seekTo = useCallback(
    async (ms) => {
      timeRef.current = ms
      setPosition(ms)
      checkpointAtRef.current = ms
      try {
        await api.seek(sessionId, ms)
        const f = await api.frame(sessionId, ms)
        strokesRef.current = f.strokes
        draw()
        onTime?.(ms, playingRef.current)
      } catch (err) {
        onError?.(String(err.message || err))
      }
    },
    [sessionId, draw, onTime, onError],
  )

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={wrapRef} className="relative min-h-0 flex-1 border border-[#222] bg-[#0e1a13]">
        <canvas ref={canvasRef} className="block h-full w-full" />
        {!sessionId && (
          <div className="absolute inset-0 flex items-center justify-center text-white/35 text-sm">
            Generate or open a lesson to start
          </div>
        )}
      </div>
      <BoardTransport
        duration={duration}
        position={position}
        disabled={!sessionId}
        onSeek={seekTo}
      />
    </div>
  )
}

function BoardTransport({ duration, position, disabled, onSeek }) {
  const [drag, setDrag] = useState(null)
  const pct = duration > 0 ? ((drag ?? position) / duration) * 100 : 0

  const fmt = (ms) => {
    const s = Math.max(0, Math.round(ms / 1000))
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  }

  return (
    <div className="mt-3 flex items-center gap-4">
      <span className="w-12 text-right text-xs text-white/50 tabular-nums">{fmt(position)}</span>
      <div
        className={`relative h-1.5 flex-1 bg-white/10 ${disabled ? 'opacity-40' : ''}`}
        role="slider"
        aria-label="Seek"
        aria-valuemin={0}
        aria-valuemax={duration}
        aria-valuenow={position}
        tabIndex={disabled ? -1 : 0}
        onPointerDown={(e) => {
          if (disabled || !duration) return
          e.currentTarget.setPointerCapture(e.pointerId)
          const rect = e.currentTarget.getBoundingClientRect()
          setDrag(((e.clientX - rect.left) / rect.width) * duration)
        }}
        onPointerMove={(e) => {
          if (drag === null || !duration) return
          const rect = e.currentTarget.getBoundingClientRect()
          setDrag(Math.max(0, Math.min(duration, ((e.clientX - rect.left) / rect.width) * duration)))
        }}
        onPointerUp={() => {
          if (drag !== null) {
            onSeek(drag)
            setDrag(null)
          }
        }}
        onKeyDown={(e) => {
          if (disabled || !duration) return
          if (e.key === 'ArrowLeft') onSeek(Math.max(0, position - 2000))
          if (e.key === 'ArrowRight') onSeek(Math.min(duration, position + 2000))
        }}
      >
        <div className="absolute inset-y-0 left-0 bg-[#ff3700]" style={{ width: `${pct}%` }} />
        <div
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white"
          style={{ left: `${pct}%` }}
        />
      </div>
      <span className="w-12 text-xs text-white/50 tabular-nums">{fmt(duration)}</span>
    </div>
  )
}
