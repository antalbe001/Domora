import { describe, expect, it } from 'vitest'
import { parseSseStream } from './chatStream'

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const events = []
  for await (const event of parseSseStream(stream)) events.push(event)
  return events
}

describe('parseSseStream', () => {
  it('reads one complete event', async () => {
    const events = await collect(
      streamOf('event: text\ndata: {"text":"Ciao"}\n\n'),
    )

    expect(events).toEqual([{ event: 'text', data: { text: 'Ciao' } }])
  })

  it('reads several events from one chunk', async () => {
    const events = await collect(
      streamOf(
        'event: text\ndata: {"text":"a"}\n\nevent: text\ndata: {"text":"b"}\n\n',
      ),
    )

    expect(events.map((e) => e.data)).toEqual([{ text: 'a' }, { text: 'b' }])
  })

  it('reassembles an event split across chunks', async () => {
    // The network decides where chunks break, not the event boundaries.
    const events = await collect(
      streamOf('event: te', 'xt\ndata: {"te', 'xt":"Ciao"}', '\n\n'),
    )

    expect(events).toEqual([{ event: 'text', data: { text: 'Ciao' } }])
  })

  it('keeps the listings payload intact', async () => {
    const events = await collect(
      streamOf(
        'event: listings\ndata: {"listings":[{"reference":"V1"}]}\n\n',
      ),
    )

    expect(events[0]).toEqual({
      event: 'listings',
      data: { listings: [{ reference: 'V1' }] },
    })
  })

  it('ignores a trailing partial event', async () => {
    const events = await collect(
      streamOf('event: text\ndata: {"text":"a"}\n\nevent: text\ndata: {"tex'),
    )

    expect(events).toHaveLength(1)
  })

  it('skips an event whose data is not valid JSON', async () => {
    const events = await collect(
      streamOf('event: text\ndata: non-json\n\nevent: done\ndata: {}\n\n'),
    )

    expect(events.map((e) => e.event)).toEqual(['done'])
  })

  it('tolerates CRLF line endings', async () => {
    const events = await collect(
      streamOf('event: text\r\ndata: {"text":"Ciao"}\r\n\r\n'),
    )

    expect(events).toEqual([{ event: 'text', data: { text: 'Ciao' } }])
  })
})
