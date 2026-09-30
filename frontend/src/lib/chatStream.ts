/**
 * Reads the backend's chat stream.
 *
 * `EventSource` cannot be used: it only issues GET requests, and a message of
 * up to 500 characters belongs in a POST body. So the SSE framing is parsed by
 * hand off `fetch`'s ReadableStream — chunk boundaries are decided by the
 * network and land anywhere, including mid-event.
 */

export type Listing = {
  reference: string
  transaction: 'sale' | 'rent'
  title: string
  url: string
  description: string | null
  price_eur: number | null
  property_type: string | null
  address: string | null
  city: string | null
  province: string | null
  surface_sqm: number | null
  bedrooms: number | null
  bathrooms: number | null
  floor_label: string | null
  energy_class: string | null
  image_url: string | null
}

export type SseEvent = { event: string; data: Record<string, unknown> }

const EVENT_SEPARATOR = /\r?\n\r?\n/

function parseEvent(block: string): SseEvent | null {
  let name = 'message'
  const dataLines: string[] = []

  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) name = line.slice('event:'.length).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice('data:'.length).trim())
  }

  if (dataLines.length === 0) return null
  try {
    return { event: name, data: JSON.parse(dataLines.join('\n')) }
  } catch {
    // A malformed event should not kill the whole stream.
    return null
  }
}

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      let separator = buffer.match(EVENT_SEPARATOR)
      while (separator?.index !== undefined) {
        const block = buffer.slice(0, separator.index)
        buffer = buffer.slice(separator.index + separator[0].length)

        const event = parseEvent(block)
        if (event) yield event

        separator = buffer.match(EVENT_SEPARATOR)
      }
    }
  } finally {
    reader.releaseLock()
  }
  // Anything left in the buffer is a truncated event: dropped on purpose.
}

export type ChatStreamHandlers = {
  onText: (text: string) => void
  onListings: (listings: Listing[]) => void
  onError: (message: string) => void
}

export const RATE_LIMITED_MESSAGE =
  'Hai inviato troppi messaggi di seguito. Attendi un momento e riprova.'
export const UNREACHABLE_MESSAGE =
  'Non riesco a contattare il server. Controlla la connessione e riprova.'

export async function sendMessage(
  sessionId: string,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal,
    })
  } catch {
    handlers.onError(UNREACHABLE_MESSAGE)
    return
  }

  if (response.status === 429) {
    handlers.onError(RATE_LIMITED_MESSAGE)
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError(UNREACHABLE_MESSAGE)
    return
  }

  for await (const { event, data } of parseSseStream(response.body)) {
    if (event === 'text') handlers.onText(String(data.text ?? ''))
    else if (event === 'listings') handlers.onListings((data.listings ?? []) as Listing[])
    else if (event === 'error') handlers.onError(String(data.message ?? UNREACHABLE_MESSAGE))
    else if (event === 'done') return
  }
}
