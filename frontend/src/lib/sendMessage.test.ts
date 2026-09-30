import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  RATE_LIMITED_MESSAGE,
  UNREACHABLE_MESSAGE,
  sendMessage,
  type Listing,
} from './chatStream'

function sseResponse(body: string, status = 200): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(body))
      controller.close()
    },
  })
  return new Response(stream, { status })
}

function handlers() {
  return {
    text: [] as string[],
    listings: [] as Listing[][],
    errors: [] as string[],
    get spies() {
      return {
        onText: (t: string) => this.text.push(t),
        onListings: (l: Listing[]) => this.listings.push(l),
        onError: (m: string) => this.errors.push(m),
      }
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('sendMessage', () => {
  it('posts the session and message to the backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse('event: done\ndata: {}\n\n'))
    vi.stubGlobal('fetch', fetchMock)

    await sendMessage('s1', 'case a Pordenone', handlers().spies)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat')
    expect(JSON.parse(init.body)).toEqual({
      session_id: 's1',
      message: 'case a Pordenone',
    })
  })

  it('reports text and listings as they arrive', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse(
          'event: text\ndata: {"text":"Ne ho "}\n\n' +
            'event: listings\ndata: {"listings":[{"reference":"V1"}]}\n\n' +
            'event: text\ndata: {"text":"trovato 1."}\n\n' +
            'event: done\ndata: {}\n\n',
        ),
      ),
    )
    const collected = handlers()

    await sendMessage('s1', 'case', collected.spies)

    expect(collected.text).toEqual(['Ne ho ', 'trovato 1.'])
    expect(collected.listings[0][0].reference).toBe('V1')
    expect(collected.errors).toEqual([])
  })

  it('turns a rate-limit refusal into a message the user can act on', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse('', 429)))
    const collected = handlers()

    await sendMessage('s1', 'case', collected.spies)

    expect(collected.errors).toEqual([RATE_LIMITED_MESSAGE])
  })

  it('surfaces a backend error event', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse('event: error\ndata: {"message":"Problema temporaneo."}\n\n'),
      ),
    )
    const collected = handlers()

    await sendMessage('s1', 'case', collected.spies)

    expect(collected.errors).toEqual(['Problema temporaneo.'])
  })

  it('survives an unreachable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed to fetch')))
    const collected = handlers()

    await sendMessage('s1', 'case', collected.spies)

    expect(collected.errors).toEqual([UNREACHABLE_MESSAGE])
  })

  it('stops reading once the stream says it is done', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse(
          'event: done\ndata: {}\n\nevent: text\ndata: {"text":"tardi"}\n\n',
        ),
      ),
    )
    const collected = handlers()

    await sendMessage('s1', 'case', collected.spies)

    expect(collected.text).toEqual([])
  })
})
