import { useEffect, useMemo, useRef, useState } from 'react'
import CursorFollower from '../components/CursorFollower.jsx'
import Header from '../components/Header.jsx'
import LibraryCanvas from '../components/LibraryCanvas.jsx'
import PopText from '../components/PopText.jsx'
import Preloader from '../components/Preloader.jsx'
import RollingText from '../components/RollingText.jsx'
import ScrollHighlight from '../components/ScrollHighlight.jsx'
import { useReveal, useSectionHoldProgress } from '../lib.js'

const HOW_STEPS = [
  {
    n: '01',
    title: 'Name a topic',
    body: 'Type any concept — Newton’s laws, Ohm’s law, limits — and pick subject, level and language.',
  },
  {
    n: '02',
    title: 'AI writes the lesson',
    body: 'A local SLM drafts narration and board actions locally. Nothing leaves your machine.',
  },
  {
    n: '03',
    title: 'Animated blackboard',
    body: 'The lesson plays as chalk writing on a vector blackboard, synced to optional speech.',
  },
  {
    n: '04',
    title: 'Checkpoints',
    body: 'The lesson pauses for questions with hints, so learning is active — not passive.',
  },
]

const BENEFITS = [
  {
    n: '01',
    title: 'Private & secure',
    body: 'All models run on your device. No cloud, no accounts, no telemetry — safe for classrooms.',
  },
  {
    n: '02',
    title: 'Three languages',
    body: 'English, Hindi and Kannada narration and board text from a single lesson source.',
  },
  {
    n: '03',
    title: 'Your material, grounded',
    body: 'Index your own PDFs and the lesson generator cites them with retrieval-augmented generation.',
  },
  {
    n: '04',
    title: 'Quality evaluation',
    body: 'Every lesson is scored and validated before it plays — format, timing and board sanity checks.',
  },
]

export default function Landing() {
  const howRef = useRef(null)
  const benefitsRef = useRef(null)
  const holds = useMemo(
    () => [
      { ref: howRef, freezeAt: 0.26 },
      { ref: benefitsRef, freezeAt: 0.62 },
    ],
    [],
  )
  const progress = useSectionHoldProgress(holds)
  const ref = useReveal()
  const [isOverBackground, setIsOverBackground] = useState(false)

  useEffect(() => {
    const onMouseMove = (e) => {
      const interactive = e.target.closest(
        'a, button, input, .pop-char, .btn-primary, .btn-ghost, .link-underline, [role="button"]'
      )
      setIsOverBackground(!interactive)
    }

    const onMouseLeave = () => setIsOverBackground(false)

    window.addEventListener('mousemove', onMouseMove, { passive: true })
    document.addEventListener('mouseleave', onMouseLeave)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseleave', onMouseLeave)
    }
  }, [])

  return (
    <div ref={ref} className="relative min-h-screen bg-black text-white">
      <CursorFollower isOverBackground={isOverBackground} />
      <Preloader />
      <Header />
      <LibraryCanvas progress={progress} isOverBackground={isOverBackground} />

      <main className="relative z-10">
        <section className="section-block gutter-x flex flex-col justify-end pb-[12vh]">
          <p className="text-eyebrow reveal mb-6">AI Blackboard · Interactive Lessons</p>
          <h1 className="text-h0 max-w-[16ch] reveal" style={{ transitionDelay: '0.1s' }}>
            <PopText text="Your AI blackboard teacher" />
          </h1>
          <div className="mt-8 max-w-xl text-lg leading-relaxed reveal" style={{ transitionDelay: '0.25s' }}>
            <ScrollHighlight
              text="Medha turns any topic into an animated chalkboard lesson — written, narrated and quizzed entirely on your machine."
              dimColor="rgba(255, 255, 255, 0.28)"
              highlightColor="#FFFFFF"
              scrollStart="top 90%"
              scrollEnd="bottom 60%"
            />
          </div>
          <div className="mt-10 flex flex-wrap items-center gap-4 reveal" style={{ transitionDelay: '0.4s' }}>
            <a href="http://medha.enter/" className="btn-primary">
              <RollingText text="Enter Studio" />
              <span aria-hidden="true">→</span>
            </a>
            <a href="#how" className="btn-ghost">
              <RollingText text="How it works" />
            </a>
          </div>
        </section>

        <section id="about" className="section-block gutter-x flex items-center">
          <div className="max-w-4xl">
            <p className="text-eyebrow reveal mb-6">Our mission</p>
            <h2 className="text-h1 reveal" style={{ transitionDelay: '0.1s' }}>
              <PopText text="Make high-quality teaching available anywhere — even without the internet." />
            </h2>
            <div className="mt-8 max-w-2xl text-lg md:text-xl leading-relaxed reveal" style={{ transitionDelay: '0.2s' }}>
              <ScrollHighlight
                text="Medha runs a small language model (SLM), a chalk-style vector renderer and speech models locally. A teacher types a topic; students watch a blackboard write itself, then answer checkpoints. No accounts. No cloud. No data leaving the room."
                dimColor="rgba(255, 255, 255, 0.25)"
                highlightColor="#FFFFFF"
                scrollStart="top 85%"
                scrollEnd="bottom 45%"
              />
            </div>
          </div>
        </section>

        <section id="how" ref={howRef} className="section-block how-hold gutter-x">
          <div className="how-sticky">
            <p className="text-eyebrow reveal mb-6">How it works</p>
            <h2 className="text-h1 max-w-[14ch] mb-16 reveal">
              <PopText text="From topic to living blackboard" />
            </h2>
            <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4">
              {HOW_STEPS.map((s, i) => (
                <article key={s.n} className="reveal" style={{ transitionDelay: `${i * 0.12}s` }}>
                  <div className="text-5xl font-light text-[#ff3700] mb-6">{s.n}</div>
                  <h3 className="text-h3 mb-3">{s.title}</h3>
                  <p className="text-white/60 leading-relaxed">{s.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <div className="journey-spacer" aria-hidden="true" />

        <section id="benefits" ref={benefitsRef} className="benefits-section gutter-x">
          <div className="benefits-grid">
            <div className="benefits-heading-col">
              <h2 className="benefits-heading">
                <PopText text="Why teams run Medha" />
              </h2>
            </div>
            <div className="benefits-cards">
              {BENEFITS.map((b) => (
                <article key={b.n} className="benefit-card reveal">
                  <span className="benefit-num">{b.n}</span>
                  <div className="benefit-body">
                    <h3 className="text-h3 mb-3">{b.title}</h3>
                    <p className="max-w-sm text-white/60 leading-relaxed">{b.body}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <footer className="relative z-10 pt-16 pb-0 bg-transparent">
          <div className="gutter-x">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center min-h-[460px] mb-12">
              {/* Left Column: Directly in the empty space next to the blackboard */}
              <div className="lg:col-span-5 flex flex-col items-start justify-center z-20">
                <p className="text-eyebrow mb-4">Ready</p>
                <h2 className="text-4xl sm:text-5xl md:text-6xl font-medium tracking-tight text-white leading-[1.05] mb-8">
                  <PopText text="Start Learning" />
                  <br />
                  <PopText text="With Medha" />
                  <br />
                  <PopText text="Today" />
                </h2>
                <div>
                  <a href="http://medha.enter/" className="btn-primary">
                    <RollingText text="Enter Classroom" />
                    <span aria-hidden="true">→</span>
                  </a>
                </div>
              </div>

              {/* Right Column: 3D blackboard space */}
              <div className="hidden lg:block lg:col-span-7 min-h-[440px] pointer-events-none" aria-hidden="true" />
            </div>

            {/* Sub-footer metadata bar */}
            <div className="border-t border-white/10 py-6 flex flex-col md:flex-row items-center justify-between gap-4 text-xs font-mono tracking-wider text-white/40">
              <div>© 2026 MEDHA. ALL RIGHTS RESERVED.</div>
              <div className="flex items-center gap-6">
                <a href="https://github.com" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">
                  APACHE-2.0
                </a>
                <span>PRIVACY</span>
              </div>
              <div>AI BLACKBOARD TEACHER</div>
            </div>
          </div>

          {/* Giant MEDHA Brand Wordmark (Zeggo-style) */}
          <div className="w-full overflow-hidden text-center select-none pointer-events-none -mb-2 sm:-mb-4 md:-mb-8">
            <span className="block text-[23vw] font-black tracking-[-0.04em] leading-[0.76] text-[#ff3700] uppercase font-sans">
              MEDHA
            </span>
          </div>
        </footer>
      </main>
    </div>
  )
}
