# Backend

FastAPI backend for the listings chatbot. Design and decisions: [`../docs/design.md`](../docs/design.md).

## Setup

```sh
uv sync --group dev
cp .env.example .env   # then fill in LLM_PROVIDER + its API key, and ADMIN_TOKEN
```

The chat model is behind a port (`app/llm/chat_model.py`); `LLM_PROVIDER` in
`.env` picks which adapter `app/dependencies.py` wires up — `anthropic` or
`gemini`. Both API keys can sit in `.env` at once; only the selected one is
used.

## Running

```sh
uv run uvicorn app.main:app --reload
```

The catalogue is read from `LISTINGS_PATH` (default `../annunci.json`) at
startup. `GET /api/health` reports how many listings are loaded.

## Tests

```sh
uv run pytest
```

> If a virtualenv from another project is active in your shell, `uv` warns and
> ignores it. Prefix with `env -u VIRTUAL_ENV` to be sure you are running
> against this project's `.venv`:
> `env -u VIRTUAL_ENV uv run pytest`

No test calls the Anthropic API — the model is faked at the `ChatModel` port.

## Endpoints

| Method | Path                 | Notes                                             |
| ------ | -------------------- | ------------------------------------------------- |
| POST   | `/api/chat`          | `{session_id, message}` → SSE stream              |
| POST   | `/api/admin/reload`  | `Authorization: Bearer $ADMIN_TOKEN`, re-reads the export |
| GET    | `/api/health`        | `{status, listings}`                              |

The chat stream sends four SSE event names: `text` (prose to append),
`listings` (cards behind the answer), `error` (a sentence to show in the chat),
and `done`.

## Layout

```
app/domain          Listing, SearchCriteria, enums — pure, no dependencies
app/normalization   location / features / fields parsers + listing_mapper
app/repositories    ListingRepository port, in-memory impl, export loader
app/services        ChatService, ConversationStore, RateLimiter
app/llm             ChatModel port, Anthropic adapter, tools, system prompt
app/api             routers, SSE encoding, request schemas
app/dependencies.py composition root
```

## Refreshing the data

```sh
cd ../scraper && python scrape_listings.py --output ../annunci.json
curl -X POST localhost:8000/api/admin/reload -H "Authorization: Bearer $ADMIN_TOKEN"
```
