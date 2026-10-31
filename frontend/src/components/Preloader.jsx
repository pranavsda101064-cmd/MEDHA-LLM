import { useEffect, useState } from 'react'

export default function Preloader() {
  const [count, setCount] = useState(0)
  const [sliding, setSliding] = useState(false)
  const [gone, setGone] = useState(false)

  useEffect(() => {
    // Prevent body scroll during preloader animation
    document.body.style.overflow = 'hidden'

    const startTime = performance.now()
    const duration = 2100 // 2.1 seconds counting up

    let rafId
    const tick = (now) => {
      const elapsed = now - startTime
      const p = Math.min(1, elapsed / duration)
      // Natural acceleration curve
      const curved = Math.pow(p, 1.15)
      const currentVal = Math.round(curved * 100)
      setCount(currentVal)

      if (p < 1) {
        rafId = requestAnimationFrame(tick)
      } else {
        // Hold at 100 briefly, then curtain slides up smoothly
        setTimeout(() => {
          setSliding(true)
          document.body.style.overflow = ''
        }, 220)
        setTimeout(() => {
          setGone(true)
        }, 1250)
      }
    }

    rafId = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(rafId)
      document.body.style.overflow = ''
    }
  }, [])

  if (gone) return null

  const formattedCount = String(count).padStart(3, '0')

  return (
    <div
      className="fixed inset-0 z-[99999] flex flex-col justify-end bg-black text-white pointer-events-auto select-none overflow-hidden"
      style={{
        transform: sliding ? 'translateY(-100%)' : 'translateY(0)',
        transition: 'transform 0.95s cubic-bezier(0.76, 0, 0.24, 1)',
        willChange: 'transform',
      }}
      aria-hidden={sliding}
    >
      <div className="gutter-x pb-10 sm:pb-14 md:pb-16 pt-8 w-full flex items-end justify-between">
        {/* Left: Tagline + Brand Logo with Liquid Color Fill */}
        <div className="flex flex-col items-start max-w-3xl">
          <p className="text-xs sm:text-sm md:text-base text-white/70 font-normal mb-3 sm:mb-4 tracking-wide">
            Your AI blackboard teacher for every classroom
          </p>

          {/* KANON: Starts red, sweeps to white as MEDHA turns red */}
          <div className="relative inline-block mb-1 sm:mb-2">
            <span className="text-xs sm:text-sm md:text-base lg:text-lg font-bold tracking-[0.25em] uppercase text-[#ff3700] select-none">
              KANON
            </span>
            <span
              className="absolute inset-0 text-xs sm:text-sm md:text-base lg:text-lg font-bold tracking-[0.25em] uppercase text-white select-none pointer-events-none"
              style={{
                clipPath: `inset(0 ${100 - count}% 0 0)`,
                transition: 'clip-path 0.04s linear',
              }}
              aria-hidden="true"
            >
              KANON
            </span>
          </div>

          <div className="relative inline-flex items-center">
            {/* White Base Layer */}
            <div className="flex items-center text-5xl sm:text-7xl md:text-8xl lg:text-9xl font-black tracking-[-0.04em] text-white select-none">
              <span>MEDHA</span>
              {/* Broadcast Waves */}
              <svg
                className="h-[0.72em] w-auto ml-2 sm:ml-3 text-white inline-block -mt-1"
                viewBox="0 0 100 100"
                fill="none"
                stroke="currentColor"
                strokeWidth="11"
                strokeLinecap="round"
              >
                <path d="M25 65 A 30 30 0 0 1 65 25" />
                <path d="M15 78 A 46 46 0 0 1 78 15" />
                <path d="M5 90 A 62 62 0 0 1 90 5" />
              </svg>
              <span className="text-[10px] sm:text-xs md:text-sm font-bold border border-white/60 rounded-full h-4 w-4 sm:h-5 sm:w-5 md:h-6 md:w-6 flex items-center justify-center ml-1.5 sm:ml-2.5 self-end mb-1 sm:mb-2 md:mb-3">
                ®
              </span>
            </div>

            {/* Orange Fill Layer (#ff3700) that wipes horizontally as count reaches 100 */}
            <div
              className="absolute inset-0 flex items-center text-5xl sm:text-7xl md:text-8xl lg:text-9xl font-black tracking-[-0.04em] text-[#ff3700] select-none pointer-events-none"
              style={{
                clipPath: `inset(0 ${100 - count}% 0 0)`,
                transition: 'clip-path 0.04s linear',
              }}
              aria-hidden="true"
            >
              <span>MEDHA</span>
              <svg
                className="h-[0.72em] w-auto ml-2 sm:ml-3 text-[#ff3700] inline-block -mt-1"
                viewBox="0 0 100 100"
                fill="none"
                stroke="currentColor"
                strokeWidth="11"
                strokeLinecap="round"
              >
                <path d="M25 65 A 30 30 0 0 1 65 25" />
                <path d="M15 78 A 46 46 0 0 1 78 15" />
                <path d="M5 90 A 62 62 0 0 1 90 5" />
              </svg>
              <span className="text-[10px] sm:text-xs md:text-sm font-bold border border-[#ff3700] rounded-full h-4 w-4 sm:h-5 sm:w-5 md:h-6 md:w-6 flex items-center justify-center ml-1.5 sm:ml-2.5 self-end mb-1 sm:mb-2 md:mb-3">
                ®
              </span>
            </div>
          </div>
        </div>

        {/* Right: Giant Digital Counter (000 -> 100) */}
        <div className="text-right pl-4 select-none">
          <span className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl font-light tracking-tight font-sans text-white tabular-nums">
            {formattedCount}
          </span>
        </div>
      </div>
    </div>
  )
}
