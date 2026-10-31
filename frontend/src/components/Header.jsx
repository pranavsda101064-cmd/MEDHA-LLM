import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import RollingText from './RollingText.jsx'

const LINKS = [
  { href: '#how', label: 'How it Works' },
  { href: '#benefits', label: 'Benefits' },
  { href: '#about', label: 'About' },
]

export default function Header() {
  const [hidden, setHidden] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const location = useLocation()

  useEffect(() => {
    let last = window.scrollY
    const onScroll = () => {
      const y = window.scrollY
      setScrolled(y > 30)
      setHidden(y > last && y > 120)
      last = y
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const onStudio = location.pathname === '/studio'

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-700 ${
        hidden ? '-translate-y-full opacity-0' : 'translate-y-0 opacity-100'
      } ${scrolled ? 'backdrop-blur-md bg-black/50 border-b border-white/10' : ''}`}
      style={{ transitionTimingFunction: 'cubic-bezier(0.625, 0.05, 0, 1)' }}
    >
      <div className="gutter-x flex items-center justify-between" style={{ height: 'var(--header-height)' }}>
        <Link to="/" className="text-h3 tracking-tight font-medium flex items-center gap-2">
          MEDHA
        </Link>
        {!onStudio && (
          <nav className="hidden md:flex items-center gap-8 text-sm text-white/80">
            {LINKS.map((l) => (
              <a key={l.href} href={l.href} className="link-underline hover:text-white">
                <RollingText text={l.label} />
              </a>
            ))}
          </nav>
        )}
        <div className="flex items-center gap-4">
          {onStudio ? (
            <Link to="/" className="text-sm link-underline text-white/80">
              <RollingText text="← Home" />
            </Link>
          ) : (
            <a href="http://medha.enter/" className="btn-primary !py-2.5 !px-6 text-sm">
              <RollingText text="Enter Studio" />
              <span aria-hidden="true">→</span>
            </a>
          )}
        </div>
      </div>
    </header>
  )
}
