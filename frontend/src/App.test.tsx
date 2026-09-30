import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

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

const ANSWER =
  'event: text\ndata: {"text":"Ne ho trovato 1."}\n\n' +
  'event: listings\ndata: {"listings":[{"reference":"V2424","transaction":"sale",' +
  '"title":"V2424 – Appartamento","url":"https://example.test/annunci/v2424/",' +
  '"description":null,"price_eur":115000,"property_type":"Appartamento",' +
  '"address":null,"city":"Pordenone","province":"PN","surface_sqm":109,' +
  '"bedrooms":2,"bathrooms":1,"floor_label":"3","energy_class":"D","image_url":null}]}\n\n' +
  'event: done\ndata: {}\n\n'

function stubBackend(body: string, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(sseResponse(body, status))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the chat page', () => {
  it('invites the visitor to describe what they are looking for', () => {
    render(<App />)

    expect(screen.getByText('Cosa stai cercando?')).toBeInTheDocument()
  })

  it('shows the question, the answer and the listing behind it', async () => {
    stubBackend(ANSWER)
    render(<App />)

    await userEvent.type(
      screen.getByLabelText('Scrivi la tua richiesta'),
      'case a Pordenone',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Invia' }))

    expect(await screen.findByText('case a Pordenone')).toBeInTheDocument()
    expect(await screen.findByText('Ne ho trovato 1.')).toBeInTheDocument()
    const card = await screen.findByRole('link')
    expect(card).toHaveAttribute('href', 'https://example.test/annunci/v2424/')
    expect(screen.getByText('115.000 €')).toBeInTheDocument()
  })

  it('sends the question when Enter is pressed', async () => {
    const fetchMock = stubBackend(ANSWER)
    render(<App />)

    await userEvent.type(
      screen.getByLabelText('Scrivi la tua richiesta'),
      'case a Sacile{Enter}',
    )

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).message).toBe('case a Sacile')
  })

  it('starts a question from one of the suggested examples', async () => {
    const fetchMock = stubBackend(ANSWER)
    render(<App />)

    await userEvent.click(
      screen.getByRole('button', { name: 'Case con giardino e box' }),
    )

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
  })

  it('clears the composer after sending', async () => {
    stubBackend(ANSWER)
    render(<App />)
    const input = screen.getByLabelText('Scrivi la tua richiesta')

    await userEvent.type(input, 'case a Pordenone{Enter}')

    await waitFor(() => expect(input).toHaveValue(''))
  })

  it('shows a rate-limit refusal in the conversation instead of failing silently', async () => {
    stubBackend('', 429)
    render(<App />)

    await userEvent.type(
      screen.getByLabelText('Scrivi la tua richiesta'),
      'case{Enter}',
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/troppi messaggi/i)
  })

  it('keeps one session across questions so follow-ups have context', async () => {
    const fetchMock = stubBackend(ANSWER)
    render(<App />)
    const input = screen.getByLabelText('Scrivi la tua richiesta')

    await userEvent.type(input, 'trilocali{Enter}')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    await userEvent.type(input, 'e con due bagni?{Enter}')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

    const [first, second] = fetchMock.mock.calls.map((call) =>
      JSON.parse(call[1].body).session_id,
    )
    expect(first).toBe(second)
  })
})
