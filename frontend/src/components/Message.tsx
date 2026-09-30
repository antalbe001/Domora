import type { Message as ChatMessage } from '../lib/useChat'
import { ListingCard } from './ListingCard'

function Thinking() {
  return (
    <span className="inline-flex gap-1 py-1" aria-label="Sto cercando">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-stone-400"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  )
}

export function Message({
  message,
  isAnswering,
}: {
  message: ChatMessage
  isAnswering: boolean
}) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-stone-800 px-4 py-2 text-white">
          {message.text}
        </p>
      </div>
    )
  }

  const isEmpty = !message.text && !message.error

  return (
    <div className="space-y-3">
      {isEmpty && isAnswering ? (
        <Thinking />
      ) : (
        message.text && (
          <p className="whitespace-pre-wrap text-stone-800">{message.text}</p>
        )
      )}

      {message.listings.length > 0 && (
        <div className="grid gap-2">
          {message.listings.map((listing) => (
            <ListingCard key={listing.reference} listing={listing} />
          ))}
        </div>
      )}

      {message.error && (
        <p
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          {message.error}
        </p>
      )}
    </div>
  )
}
