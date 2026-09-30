# Frontend

React + Vite + TypeScript + Tailwind. A single chat page that talks to the
backend's SSE stream. Design and decisions: [`../docs/design.md`](../docs/design.md).

## Setup

```sh
npm install
```

> **Use npm 12 or newer.** npm 10.9.x crashes resolving this dependency tree
> (`Cannot read properties of null (reading 'edgesOut')`, a bug in its peer
> resolver). Without upgrading globally: `npx npm@12 install`.

## Running

```sh
npm run dev          # http://localhost:5173
```

`/api` is proxied to `http://localhost:8000`, so start the backend too
(see [`../backend/README.md`](../backend/README.md)).

## Tests

```sh
npm test             # vitest run
npm run test:watch
```

No test touches the network: `fetch` is stubbed with a scripted SSE stream.

## How the stream is read

`EventSource` cannot be used — it only issues GET requests, and a message of up
to 500 characters belongs in a POST body. So `src/lib/chatStream.ts` parses the
SSE framing by hand off `fetch`'s `ReadableStream`; chunk boundaries come from
the network and can land mid-event, which is what most of its tests are about.

Four event names arrive: `text` (prose to append), `listings` (cards behind the
answer), `error` (a sentence to show in the chat) and `done`.

## Layout

```
src/lib/chatStream.ts   SSE parsing + sendMessage
src/lib/useChat.ts      conversation state
src/lib/session.ts      session id, persisted in localStorage
src/lib/format.ts       prices and listing facts, in Italian
src/components/         Message, ListingCard, Composer
src/App.tsx             the page
```
