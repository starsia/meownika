import json
import os
import uuid

import anthropic
import redis
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

load_dotenv()
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Ensure frontend origins are allowed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "You love cats! Nika also loves cats, and they like to see them when they are bored. "
    "Address the user as Nika. When responding to Nika, do not include URLs in your text "
    "response. Instead, provide the cat picture URLs as tool outputs, and focus your text "
    "response on engaging stories or descriptions about cats."
)

CAT_API_KEY = os.getenv("CAT_API_KEY")
CAT_API_URL = "https://api.thecatapi.com/v1"

# Per-session conversation history, stored in Redis instead of process memory so
# it survives server restarts/reloads and works across multiple backend instances.
# Keyed by session_id, sent by the frontend and generated fresh on each page load.
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
SESSION_TTL_SECONDS = 60 * 60 * 24  # sessions expire after a day of inactivity


def load_session(session_id):
    raw = redis_client.get(f"session:{session_id}")
    return json.loads(raw) if raw else []


def save_session(session_id, messages):
    redis_client.set(f"session:{session_id}", json.dumps(messages), ex=SESSION_TTL_SECONDS)

TOOLS = [
    {
        "name": "get_cat_photo_url",
        # prevent user asking for negative cat photos...
        "description": "Gets the url to a random cat photo from CATAPI, but if the user asks for less than 1 cat picture, respond with 1 cat picture, and say they need to ask for at least one.",
        "input_schema": {
            "type": "object",
            "properties": {
                "quantity": {
                    "type": "integer",
                    "description": "The number of cat photo urls to fetch",
                    "default": 1,
                }
            },
            "required": ["quantity"],
        },
    }
]


def get_cat_photo_url(quantity):
    """Fetch the URLs to random cat photos from The Cat API."""
    try:
        headers = {"x-api-key": CAT_API_KEY}
        response = requests.get(f"{CAT_API_URL}/images/search?limit={quantity}", headers=headers)
        response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)
        data = response.json()
        if data:
            return [item['url'] for item in data]  # Extract all image URLs
        return []
    except requests.exceptions.RequestException as e:
        return f"Error fetching cat photos: {e}"


def send_and_run(session_id, content):
    """Run one turn of the conversation, handling a single round of tool use."""
    messages = load_session(session_id)
    messages.append({"role": "user", "content": content})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    local_paths = []

    if response.stop_reason == "tool_use":
        # .model_dump() converts the SDK's content blocks to plain dicts so the
        # history is JSON-serializable for Redis (and still valid as API input).
        messages.append({"role": "assistant", "content": [b.model_dump() for b in response.content]})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            urls = get_cat_photo_url(**block.input)
            local_paths = download_images(urls) if isinstance(urls, list) else []

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(local_paths),
            })

        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

    messages.append({"role": "assistant", "content": [b.model_dump() for b in response.content]})
    save_session(session_id, messages)

    text = next((b.text for b in response.content if b.type == "text"), "")
    return {"text": text, "images": local_paths}


def render_history(messages):
    """Turn raw Claude message history back into {sender, text, images} chat bubbles."""
    bubbles = []
    pending_images = []

    for message in messages:
        role, content = message["role"], message["content"]

        if role == "user" and isinstance(content, str):
            bubbles.append({"sender": "user", "text": content, "images": []})
        elif role == "user" and isinstance(content, list):
            # tool_result blocks: content is a JSON-encoded list of image paths
            for block in content:
                if block.get("type") == "tool_result":
                    pending_images.extend(json.loads(block["content"]))
        elif role == "assistant":
            text = next((b["text"] for b in content if b.get("type") == "text"), "")
            if text:
                bubbles.append({"sender": "bot", "text": text, "images": pending_images})
                pending_images = []

    return bubbles


def download_images(urls, folder="cat_pictures"):
    os.makedirs(folder, exist_ok=True)
    local_paths = []
    for url in urls:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            file_path = os.path.join(folder, f"cat_{uuid.uuid4().hex}.jpg")
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)

            local_paths.append(f"/cat_pictures/{os.path.basename(file_path)}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {url}: {e}")

    return local_paths


# Serve static images from the 'cat_pictures' directory
os.makedirs("cat_pictures", exist_ok=True)
app.mount("/cat_pictures", StaticFiles(directory="cat_pictures"), name="cat_pictures")


class AssistantRequest(BaseModel):
    message: str  # Example: "I want 3 cats"
    session_id: str | None = None  # Frontend-generated; new session if omitted


@app.post("/cats_now/")
async def cats_now(request: AssistantRequest):
    """Handles a chat turn with Claude, returning text and any cat image URLs."""
    session_id = request.session_id or str(uuid.uuid4())
    try:
        output = send_and_run(session_id, request.message)
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e.message}")
    output["session_id"] = session_id
    return output


@app.get("/session/{session_id}")
async def get_session_history(session_id: str):
    """Returns the chat bubbles for a previously started session, for reload/resume."""
    return {"messages": render_history(load_session(session_id))}


# Allow script to start the FastAPI server automatically
# Otherwise, use uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    # run on all active ip addresses, 8000 is default port for FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)
