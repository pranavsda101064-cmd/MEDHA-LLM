export default function PopText({ text, className = '' }) {
  if (!text) return null
  const words = text.split(' ')

  return (
    <span className={`inline ${className}`}>
      {words.map((word, wIdx) => (
        <span key={wIdx} className="inline-block whitespace-nowrap">
          {word.split('').map((char, cIdx) => (
            <span
              key={cIdx}
              className="pop-char"
              aria-hidden="true"
            >
              {char}
            </span>
          ))}
          {wIdx < words.length - 1 && (
            <span className="inline-block" aria-hidden="true">
              &nbsp;
            </span>
          )}
        </span>
      ))}
      <span className="sr-only">{text}</span>
    </span>
  )
}
