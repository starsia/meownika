import json
import os
import uuid

import anthropic
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

# In-memory per-session conversation history. Keyed by session_id, sent by the
# frontend and generated fresh on each page load. Not persisted across restarts.
sessions: dict[str, list] = {}

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
    messages = sessions.setdefault(session_id, [])
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
        messages.append({"role": "assistant", "content": response.content})

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

    messages.append({"role": "assistant", "content": response.content})

    text = next((b.text for b in response.content if b.type == "text"), "")
    return {"text": text, "images": local_paths}


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


# Allow script to start the FastAPI server automatically
# Otherwise, use uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    # run on all active ip addresses, 8000 is default port for FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)
