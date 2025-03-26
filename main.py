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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = openai.Client()
model = "gpt-4o-mini"

CAT_API_KEY = "live_YOUR_CAT_API_KEY"  # Add your Cat API key here
CAT_API_URL = "https://api.thecatapi.com/v1"

def get_cat_image(breed_id):
    headers = {"x-api-key": CAT_API_KEY}
    response = requests.get(f"{CAT_API_URL}/images/search?breed_ids={breed_id}", headers=headers)
    if response.ok:
        return response.json()[0]["url"]
    return None

def get_breed_id(breed_name):
    headers = {"x-api-key": CAT_API_KEY}
    response = requests.get(f"{CAT_API_URL}/breeds/search?q={breed_name}", headers=headers)
    if response.ok and response.json():
        return response.json()[0]["id"]
    return None

# Define available functions
available_functions = {
    "get_cat_image": {
        "name": "get_cat_image",
        "description": "Get an image of a specific cat breed",
        "parameters": {
            "type": "object",
            "properties": {
                "breed_name": {
                    "type": "string",
                    "description": "The name of the cat breed"
                }
            },
            "required": ["breed_name"]
        }
    }
}

# Initialize assistant with function calling
assistant = client.beta.assistants.create(
    name="MeowNika",
    instructions="You are a cat expert. When users ask about cat breeds, provide information and show images when requested.",
    model=model,
    tools=[{"type": "function", "function": available_functions["get_cat_image"]}]
)

# Store thread IDs
threads = {}

class ChatMessage(BaseModel):
    message: str
    thread_id: str = "thread_pF2QmEYdF009PiVcYWAmkoGF"  # Fix default value

@app.get("/")
def read_root():
    return {"Hello": "World"}

class Item(BaseModel):
    name: str
    description: str = None
    price: float
    tax: float = None

@app.post("/items/")
def create_item(item: Item):
    return item

@app.post("/chat")
async def chat(chat_message: ChatMessage):
    try:
        print(f"Received message: {chat_message.message}")
        print(f"Thread ID: {chat_message.thread_id}")
        
        if chat_message.thread_id == "null" or not chat_message.thread_id:
            print("Creating new thread")
            thread = client.beta.threads.create()
            thread_id = thread.id
        else:
            thread_id = chat_message.thread_id
        
        print(f"Using thread ID: {thread_id}")

        # Add message to thread
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=chat_message.message
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant.id,
            instructions="Please address the user as Nika."
        )

        # Wait for run completion
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            
            if run_status.status == 'requires_action':
                # Handle function calling
                tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                
                for tool_call in tool_calls:
                    if tool_call.function.name == "get_cat_image":
                        breed_name = eval(tool_call.function.arguments)["breed_name"]
                        breed_id = get_breed_id(breed_name)
                        image_url = get_cat_image(breed_id) if breed_id else None
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": image_url if image_url else "No image found for this breed."
                        })

                # Submit outputs back to assistant
                run = client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            elif run_status.status == 'completed':
                messages = client.beta.threads.messages.list(thread_id=thread_id)
                return {
                    "thread_id": thread_id,
                    "response": messages.data[0].content[0].text.value,
                    "image_url": tool_outputs[0]["output"] if 'tool_outputs' in locals() else None
                }
            elif run_status.status == 'failed':
                raise HTTPException(status_code=500, detail="Assistant failed to respond")

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # run on all active ip addresses, 8000 is default port for FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)