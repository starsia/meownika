import json
import re
import time
import openai
import os
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

client = openai.Client()
model = "gpt-4o-mini"

CAT_API_KEY = os.getenv("CAT_API_KEY")
CAT_API_URL = "https://api.thecatapi.com/v1"


def get_cat_photo_url(quantity):
    """Fetch the URLs to random cat photos from The Cat API."""
    urls = []
    try:
        headers = {"x-api-key": CAT_API_KEY}
        response = requests.get(f"{CAT_API_URL}/images/search?limit={quantity}", headers=headers)
        # response = requests.get(f"{CAT_API_URL}/images/search?limit={quantity}&breed_ids={breed_ids}", headers=headers)
        response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)
        data = response.json()
        if data:
            urls = [item['url'] for item in data]  # Extract all image URLs
            return urls
        return "No cat photos found."
    except requests.exceptions.RequestException as e:
        return f"Error fetching cat photos: {e}"

# Example usage
# print(get_cat_photo_url(2))


# Define the tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_cat_photo_url",
            # prevent user asking for negative cat photos...
            "description": "Gets the url to a random cat photo from CATAPI, but if the user asks for less than 1 cat picture, respond with 1 cat picture, and say they need to ask for at least one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "quantity": {
                        "type": "integer",
                        "description": "The number of cat photo urls to fetch",
                        "default": 1,
                    }
                },
                "required": [
                    "quantity"
                ]
            },
        }
    }
]

# Initialize assistant with function calling tools
assistant = client.beta.assistants.create(
    name="MeowNika",
    instructions=(
        "You love cats! Nika also loves cats, and they like to see them when they are bored. "
        "When responding to Nika, do not include URLs in your text response. "
        "Instead, provide the cat picture URLs as tool outputs, and focus your text response "
        "on engaging stories or descriptions about cats."
    ),
    model=model,
    tools=tools
)

# # Delete all photos in the 'cat_pictures' directory
# folder = "cat_pictures"
# if os.path.exists(folder):
#     for file in os.listdir(folder):
#         file_path = os.path.join(folder, file)
#         try:
#             if os.path.isfile(file_path):
#                 os.unlink(file_path)  # Remove the file
#         except Exception as e:
#             print(f"Failed to delete {file_path}: {e}")

thread = client.beta.threads.create()

def wait_on_run(run):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        
        time.sleep(0.5)
    return run

# Create a message with content as argument and return a run
def send_and_run(content):
    # Check if there's an active run in the thread
    active_runs = client.beta.threads.runs.list(thread_id=thread.id)
    for run in active_runs:
        if run.status in ["queued", "in_progress"]:
            # Wait for the active run to complete
            wait_on_run(run)

    # Create a new message
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content,
    )
    
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Please address the user as Nika."
    )

    # Wait for completion
    run = wait_on_run(run)

    # Initialize tool outputs and local paths
    tool_outputs = []
    local_paths = []

    if run.status == "requires_action":
        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            # Call the Function from our Python code
            task = get_cat_photo_url(**arguments)

            # Download images and get their local paths
            local_paths = download_images(task)

            # Add the tool output for this call
            tool_outputs.append({
                "tool_call_id": tool_call.id,
                "output": json.dumps(local_paths),
            })

        # Submit all tool outputs at once
        run = client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=tool_outputs,
        )

        run = wait_on_run(run)

    if run.status == 'completed': 
        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        
        for message in messages:
            if message.role == "assistant":
                return {
                    "text": message.content[0].text.value,
                    "images": local_paths if local_paths else []  # Ensure images is an empty list if no images
                }
    else:
        return {"text": f"Something went wrong, here's the run status: {run.status}", "images": []}

def download_images(urls, folder="cat_pictures"):
    # Ensure the folder exists
    os.makedirs(folder, exist_ok=True)
    
    local_paths = []
    existing_files = os.listdir(folder)
    existing_count = len(existing_files)
    
    for i, url in enumerate(urls):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            file_path = os.path.join(folder, f"cat_{existing_count + i + 1}.jpg")
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            
            local_paths.append(f"/cat_pictures/{os.path.basename(file_path)}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {url}: {e}")
    
    return local_paths

# Serve static images from the 'cat_pictures' directory
app.mount("/cat_pictures", StaticFiles(directory="cat_pictures"), name="cat_pictures")

@app.get("/get_cat_pictures")
def get_cat_pictures():
    images = os.listdir("cat_pictures")
    return {"images": [f"/cat_pictures/{img}" for img in images]}

# Example usage:
# picture_urls = ["https://cdn2.thecatapi.com/images/7pk.gif", "https://cdn2.thecatapi.com/images/bqv.jpg"]
# download_images(picture_urls)


# POST endpoint for interacting with OpenAI Assistant
class AssistantRequest(BaseModel):
    message: str  # Example: "I want 3 cats"

@app.post("/cats_now/")
async def cats_now(request: AssistantRequest):
    """Handles requests to OpenAI Assistant for cat image URLs."""
    output = send_and_run(request.message)
    return output

# Allow script to start the FastAPI server automatically
# Otherwise, use uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    # run on all active ip addresses, 8000 is default port for FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)


# # Store thread IDs
# threads = {}

# def get_cat_image(breed_id):
#     headers = {"x-api-key": CAT_API_KEY}
#     response = requests.get(f"{CAT_API_URL}/images/search?breed_ids={breed_id}", headers=headers)
#     if response.ok:
#         return response.json()[0]["url"]
#     return None

# def get_breed_id(breed_name):
#     headers = {"x-api-key": CAT_API_KEY}
#     response = requests.get(f"{CAT_API_URL}/breeds/search?q={breed_name}", headers=headers)
#     if response.ok and response.json():
#         return response.json()[0]["id"]
#     return None


# print(client.beta.threads.messages.list(thread_id=thread.id, order="asc"))