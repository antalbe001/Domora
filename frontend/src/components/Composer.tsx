import { useState } from 'react'

export const MAX_MESSAGE_LENGTH = 500

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void
  disabled: boolean
}) {
  const [draft, setDraft] = useState('')
  const canSend = draft.trim().length > 0 && !disabled

  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSend) return
    onSend(draft)
    setDraft('')
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <div className="flex-1">
        <label htmlFor="message" className="sr-only">
          Scrivi la tua richiesta
        </label>
        <textarea
          id="message"
          value={draft}
          onChange={(event) => setDraft(event.target.value.slice(0, MAX_MESSAGE_LENGTH))}
          onKeyDown={(event) => {
            // Enter sends; Shift+Enter is a newline.
            if (event.key === 'Enter' && !event.shiftKey) submit(event)
          }}
          rows={1}
          placeholder="Es. trilocale a Pordenone sotto i 150.000 € con box"
          className="w-full resize-none rounded-xl border border-stone-300 bg-white px-4 py-3 text-stone-900 placeholder:text-stone-400 focus:border-stone-500 focus:outline-none"
        />
        {draft.length > MAX_MESSAGE_LENGTH - 50 && (
          <p className="mt-1 text-xs text-stone-500">
            {MAX_MESSAGE_LENGTH - draft.length} caratteri rimasti
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={!canSend}
        className="rounded-xl bg-stone-800 px-5 py-3 font-medium text-white transition enabled:hover:bg-stone-900 disabled:cursor-not-allowed disabled:bg-stone-300"
      >
        Invia
      </button>
    </form>
  )
}
