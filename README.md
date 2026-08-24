# meownika
A cat chatbot that uses the Claude API (Anthropic) to display different cats to make Nika staff feel more motivated to work.

## Setup

1. `pip install -r requirements.txt`
2. Create a `.env` file with:
   ```
   ANTHROPIC_API_KEY=your-key-here
   CAT_API_KEY=your-cat-api-key-here
   REDIS_URL=redis://localhost:6379/0   # optional, this is the default
   ```
3. Start Redis: `docker compose up -d` (or run your own `redis-server`)
4. `uvicorn main:app --reload` (or `python main.py`)
5. `cd frontend && npm install && npm run dev`

## Changelog

### 2026-08-26 — Resume conversation on page reload

Redis persisted conversation history server-side, but a browser refresh still lost
the chat because `sessionId` and the on-screen messages were only ever kept in React
state, which resets on reload. The frontend never had a reason to ask the backend for
history — there was no way to ask.

- Added `GET /session/{session_id}`, which reconstructs `{sender, text, images}` chat
  bubbles from the raw Redis history.
- `sessionId` is now saved to `localStorage` (just the ID string — the actual
  conversation data still lives only in Redis) and reloaded on page load, which
  triggers a fetch of that session's history to repopulate the chat.

### 2026-08-26 — Session history moved to Redis

Conversation history was previously kept in a plain Python dict (`sessions = {}`) in
server memory. That meant every conversation was lost on server restart (including
every `--reload` triggered by a code save), and it wouldn't work correctly if the app
ever ran as more than one process.

- Session history now lives in Redis (`docker-compose.yml` adds a `redis` service),
  keyed as `session:<session_id>`, serialized as JSON, with a 24-hour TTL so idle
  sessions expire on their own instead of accumulating forever.
- The backend is now stateless — any request can be handled by any backend instance,
  since the actual state lives in Redis rather than in that instance's memory.
- Fixed a latent serialization bug this surfaced: Claude's response content blocks
  are SDK objects, not plain dicts. They happened to work when kept in a Python-native
  dict, but needed `.model_dump()` to become JSON-safe for Redis (and remain valid
  input for the next API call either way).

### 2026-08-25 — Switched frontend styling to Tailwind CSS

Replaced hand-written CSS (`App.css`, most of `index.css`) with Tailwind utility
classes directly in JSX. Added `@tailwindcss/vite` — Tailwind v4's Vite plugin, which
needs no separate `tailwind.config.js` or PostCSS setup.

### 2026-08-25 — UI cleanup

The original JSX referenced Tailwind utility classes (`bg-blue-500`, `flex-grow`, ...)
but Tailwind was never actually installed, so those classes did nothing — all real
styling came from a mismatched `index.css`. Rewrote the chat UI with consistent,
working CSS: proper chat bubbles, a typing indicator while waiting on a response,
Enter-to-send, disabled input while a request is in flight, and auto-scroll to the
latest message. (This pass predates the Tailwind migration above and originally used
hand-written CSS, since replaced.)

### 2026-08-25 — Migrated from OpenAI Assistants API to Claude

The original implementation used OpenAI's Assistants API (`gpt-4o-mini`), which is
deprecated in favor of the Responses API, and had a couple of structural bugs. This
revamp moves to the Claude Messages API (`claude-haiku-4-5`) with a simpler, more
correct design:

- **Dropped the Assistants/Threads/Runs machinery.** No more `assistants.create` /
  `threads.create` / polling loop (`wait_on_run`). A chat turn is now one or two plain
  `client.messages.create()` calls: send the message, and if Claude wants to call the
  `get_cat_photo_url` tool, send the tool result back and get the final response —
  no polling, no busy-wait `time.sleep(0.5)`.
- **Fixed shared-conversation bug.** The old code created a single global `thread` at
  server startup, so every user's messages landed in the same conversation. Backend now
  keeps a per-`session_id` message history (in-memory dict); the frontend generates a
  session on first reply and sends it back on every request.
- **Fixed image filename collisions.** Downloaded cat photos are now named with a
  UUID instead of a running count of files in the folder, so concurrent requests can't
  clobber each other.
- **Model:** `claude-haiku-4-5` — fast and inexpensive, appropriate for a single-tool
  chat task like this.

Known limitations carried forward from the original design (not addressed in this pass,
since they're out of scope for an API migration): session history was in-memory only
at the time (later fixed — see the Redis entry above), and the frontend still
hardcodes `http://localhost:8000`.
