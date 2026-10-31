import { useEffect, useRef, useState } from 'react'

export default function CursorFollower({ isOverBackground }) {
  const [visible, setVisible] = useState(false)
  const cursorRef = useRef(null)
  const pos = useRef({ x: -100, y: -100 })
  const target = useRef({ x: -100, y: -100 })
  const rafId = useRef(null)

  useEffect(() => {
    // Only enable on devices with fine pointer (mouse)
    if (!window.matchMedia('(pointer: fine)').matches) return

    const onMouseMove = (e) => {
      target.current.x = e.clientX
      target.current.y = e.clientY
      if (!visible) setVisible(true)
    }

    const onMouseLeave = () => {
      setVisible(false)
    }

    window.addEventListener('mousemove', onMouseMove, { passive: true })
    document.addEventListener('mouseleave', onMouseLeave)

    const loop = () => {
      // Smooth lerp trailing movement
      pos.current.x += (target.current.x - pos.current.x) * 0.18
      pos.current.y += (target.current.y - pos.current.y) * 0.18

      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate3d(${pos.current.x}px, ${pos.current.y}px, 0) translate(-50%, -50%)`
      }
      rafId.current = requestAnimationFrame(loop)
    }
    rafId.current = requestAnimationFrame(loop)

    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseleave', onMouseLeave)
      if (rafId.current) cancelAnimationFrame(rafId.current)
    }
  }, [visible])

  if (!visible) return null

  return (
    <div
      ref={cursorRef}
      className="pointer-events-none fixed top-0 left-0 z-50 rounded-full transition-[width,height,background-color,border-color,box-shadow] duration-300 ease-out"
      style={{
        width: isOverBackground ? '48px' : '16px',
        height: isOverBackground ? '48px' : '16px',
        backgroundColor: isOverBackground ? 'rgba(255, 55, 0, 0.08)' : 'rgba(255, 55, 0, 0.4)',
        borderColor: isOverBackground ? 'rgba(255, 55, 0, 0.65)' : 'rgba(255, 255, 255, 0.4)',
        borderWidth: '1.5px',
        borderStyle: 'solid',
        boxShadow: isOverBackground
          ? '0 0 25px rgba(255, 55, 0, 0.35), inset 0 0 15px rgba(255, 55, 0, 0.12)'
          : '0 0 8px rgba(255, 55, 0, 0.3)',
      }}
      aria-hidden="true"
    />
  )
}
