import json
import time
import openai
import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    # allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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



# @app.get("/get-cats")
# def get_cats(quantity: int = 1):
#     urls = get_cat_photo_url(quantity)
#     return {"urls": urls}

# Define the tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_cat_photo_url",
            # prevent user asking for negative cat photos...
            "description": "Get the url to a random cat photo from CATAPI, but if the user asks for less than 1 cat picture, respond with 1 cat picture, and say they need to ask for at least one.",
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
    instructions="You are a cat expert. When users ask about cat breeds, provide information and show images when requested.",
    model=model,
    tools=tools
)

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

    # Initialize task as None
    task = None

    if run.status == "requires_action":
        tool_call = run.required_action.submit_tool_outputs.tool_calls[0]
        name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        # Call the Function from our Python code
        task = get_cat_photo_url(**arguments)

        # Inform the model that the Function was called
        run = client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=[
                {
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(task),
                }
            ],
        )

        run = wait_on_run(run)

    if run.status == 'completed': 
        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        return messages
    else:
        return f"Something went wrong, here's the run status: {run.status}"



# POST endpoint for interacting with OpenAI Assistant
class AssistantRequest(BaseModel):
    message: str  # Example: "I want 3 cats"

@app.post("/cats-now")
def get_cats_now(request: AssistantRequest):
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