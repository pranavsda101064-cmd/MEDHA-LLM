import { useState } from 'react'

export default function CheckpointModal({ checkpoint, onContinue }) {
  const [showAnswer, setShowAnswer] = useState(false)
  const [hintIndex, setHintIndex] = useState(0)

  if (!checkpoint) return null

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-6">
      <div className="w-full max-w-lg border border-[#333] bg-[#0a0a0a] p-8">
        <p className="text-eyebrow mb-4">Checkpoint</p>
        <h3 className="text-h3 mb-6">{checkpoint.question}</h3>

        {checkpoint.hints?.length > 0 && (
          <div className="mb-6">
            <button
              type="button"
              className="btn-ghost !py-2 !px-4 text-xs"
              onClick={() => setHintIndex((i) => Math.min(i + 1, checkpoint.hints.length))}
              disabled={hintIndex >= checkpoint.hints.length}
            >
              Hint {Math.min(hintIndex + 1, checkpoint.hints.length)}/{checkpoint.hints.length}
            </button>
            {hintIndex > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-white/60">
                {checkpoint.hints.slice(0, hintIndex).map((h, i) => (
                  <li key={i}>· {h}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {showAnswer ? (
          <p className="mb-6 border border-[#333] p-4 text-chalk font-mono">{checkpoint.expected}</p>
        ) : (
          <button
            type="button"
            className="mb-6 text-sm text-white/50 link-underline"
            onClick={() => setShowAnswer(true)}
          >
            Show answer
          </button>
        )}

        <button type="button" className="btn-primary w-full justify-center" onClick={onContinue}>
          Continue lesson
        </button>
      </div>
    </div>
  )
}
