# meownika
A cat chatbot that uses the Claude API (Anthropic) to display different cats to make Nika staff feel more motivated to work.

## Setup

1. `pip install -r requirements.txt`
2. Create a `.env` file with:
   ```
   ANTHROPIC_API_KEY=your-key-here
   CAT_API_KEY=your-cat-api-key-here
   ```
3. `uvicorn main:app --reload` (or `python main.py`)
4. `cd frontend && npm install && npm run dev`

## Changelog

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
since they're out of scope for an API migration): session history is in-memory only
(lost on server restart), and the frontend still hardcodes `http://localhost:8000`.
