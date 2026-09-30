const STORAGE_KEY = 'chat-session-id'

/**
 * A session id that survives a reload so follow-up questions keep their
 * context. Falls back to a fresh per-load id when storage is unavailable
 * (private windows, blocked site data) — the chat still works, it just
 * forgets on reload.
 */
export function getSessionId(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return stored
    const created = crypto.randomUUID()
    localStorage.setItem(STORAGE_KEY, created)
    return created
  } catch {
    return crypto.randomUUID()
  }
}
