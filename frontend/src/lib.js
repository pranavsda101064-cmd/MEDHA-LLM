import { useEffect, useRef, useState } from 'react'

export function useScrollProgress() {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    let raf = 0
    const update = () => {
      raf = 0
      const doc = document.documentElement
      const max = doc.scrollHeight - window.innerHeight
      setProgress(max > 0 ? window.scrollY / max : 0)
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  return progress
}

export function useSectionHoldProgress(holds, freezeAt = null) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const zones = Array.isArray(holds)
      ? holds
      : [{ ref: holds, freezeAt }]
    let raf = 0
    const update = () => {
      raf = 0
      const doc = document.documentElement
      const max = doc.scrollHeight - window.innerHeight
      if (max <= 0) {
        setProgress(0)
        return
      }
      const scrollY = window.scrollY
      const keys = [[0, 0]]
      for (const zone of zones) {
        const el = zone.ref?.current
        if (!el) continue
        const top = el.getBoundingClientRect().top + scrollY
        const height = el.offsetHeight
        const holdStart = Math.max(0, top - window.innerHeight * 0.35)
        const holdEnd = Math.max(holdStart + 1, top + height - window.innerHeight * 0.65)
        const frozen = zone.freezeAt ?? holdStart / max
        keys.push([holdStart, frozen], [holdEnd, frozen])
      }
      keys.push([max, 1])
      for (let i = 1; i < keys.length; i++) {
        if (keys[i][0] <= keys[i - 1][0]) keys[i][0] = keys[i - 1][0] + 1
      }
      let i = 0
      while (i < keys.length - 2 && scrollY > keys[i + 1][0]) i++
      const [sa, pa] = keys[i]
      const [sb, pb] = keys[i + 1]
      const t = clamp((scrollY - sa) / Math.max(1, sb - sa), 0, 1)
      setProgress(lerp(pa, pb, t))
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [holds, freezeAt])

  return progress
}

export function useReveal() {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) entry.target.classList.add('is-visible')
        })
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' },
    )
    el.querySelectorAll('.reveal').forEach((node) => io.observe(node))
    return () => io.disconnect()
  }, [])
  return ref
}

export function lerp(a, b, t) {
  return a + (b - a) * t
}

export function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v))
}

export function smoothstep(t) {
  const x = clamp(t, 0, 1)
  return x * x * (3 - 2 * x)
}

export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

