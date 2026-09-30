import { useEffect, useRef } from 'react'
import { Composer } from './components/Composer'
import { Message } from './components/Message'
import { useChat } from './lib/useChat'

const EXAMPLES = [
  'Trilocale a Pordenone sotto i 150.000 €',
  'Cosa avete in affitto a Cordenons?',
  'Case con giardino e box',
]

function Empty({ onPick }: { onPick: (example: string) => void }) {
  return (
    <div className="py-10 text-center">
      <h2 className="text-lg font-medium text-stone-800">
        Cosa stai cercando?
      </h2>
      <p className="mx-auto mt-1 max-w-sm text-sm text-stone-500">
        Descrivilo come lo diresti a voce: zona, budget, quante camere.
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onPick(example)}
            className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-700 transition hover:border-stone-400 hover:bg-stone-50"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  const { messages, isAnswering, ask } = useChat()
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  return (
    <div className="flex min-h-dvh flex-col bg-stone-50">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-4">
          <h1 className="font-medium text-stone-900">Cerca casa</h1>
          <p className="text-sm text-stone-500">
            Chiedi in linguaggio naturale: rispondo solo sugli immobili disponibili.
          </p>
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl flex-1 px-4">
        <div className="space-y-6 py-6">
          {messages.length === 0 ? (
            <Empty onPick={ask} />
          ) : (
            messages.map((message, index) => (
              <Message
                key={index}
                message={message}
                isAnswering={isAnswering && index === messages.length - 1}
              />
            ))
          )}
          <div ref={bottom} />
        </div>
      </main>

      <div className="sticky bottom-0 border-t border-stone-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-3">
          <Composer onSend={ask} disabled={isAnswering} />
        </div>
      </div>
    </div>
  )
}
