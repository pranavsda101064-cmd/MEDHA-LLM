export default function RollingText({ text, className = '' }) {
  return (
    <span className={`rolling-line ${className}`}>
      {text.split('').map((char, i) => (
        <span
          key={i}
          className="char"
          style={{ '--char-index': i }}
          aria-hidden="true"
        >
          {char === ' ' ? '\u00A0' : char}
        </span>
      ))}
      <span className="sr-only">{text}</span>
    </span>
  )
}
