import { useCallback, useRef, useState } from 'react'
import { sendMessage, type Listing } from './chatStream'
import { getSessionId } from './session'

export type Message =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; listings: Listing[]; error?: string }

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isAnswering, setIsAnswering] = useState(false)
  const sessionId = useRef(getSessionId())

  const updateAnswer = useCallback(
    (update: (answer: Extract<Message, { role: 'assistant' }>) => void) => {
      setMessages((current) => {
        const next = [...current]
        const answer = next[next.length - 1]
        if (answer?.role !== 'assistant') return current
        const copy = { ...answer, listings: [...answer.listings] }
        update(copy)
        next[next.length - 1] = copy
        return next
      })
    },
    [],
  )

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim()
      if (!text || isAnswering) return

      setMessages((current) => [
        ...current,
        { role: 'user', text },
        { role: 'assistant', text: '', listings: [] },
      ])
      setIsAnswering(true)

      try {
        await sendMessage(sessionId.current, text, {
          onText: (chunk) =>
            updateAnswer((answer) => {
              answer.text += chunk
            }),
          onListings: (listings) =>
            updateAnswer((answer) => {
              answer.listings.push(...listings)
            }),
          onError: (message) =>
            updateAnswer((answer) => {
              answer.error = message
            }),
        })
      } finally {
        setIsAnswering(false)
      }
    },
    [isAnswering, updateAnswer],
  )

  return { messages, isAnswering, ask }
}
