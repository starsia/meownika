import openai
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from uuid import UUID, uuid4

load_dotenv()
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origins=["http://localhost:5173",
    "localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = openai.Client()
model = "gpt-4o-mini"

# Initialize assistant
assistant = client.beta.assistants.create(
    name="MeowNika",
    instructions="you are a cat master, and you know all the cats in the world. your user will prompt you with cat breeds, and you will respond with a fun fact about that breed.",
    model=model
)

# Store thread IDs
threads = {}
messages = {}

class ChatMessage(BaseModel):
    message: str
    thread_id: str = "thread_pF2QmEYdF009PiVcYWAmkoGF"  # Fix default value


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
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant.id,
            instructions="Please address the user as Nika."
        )

        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id=thread_id
            )
            return {
                "thread_id": thread_id,
                "response": messages.data[0].content[0].text.value
            }
        else:
            raise HTTPException(status_code=500, detail="Assistant failed to respond")

    except Exception as e:
        print(f"Error occurred: {str(e)}")  # Add error logging
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # run on all active ip addresses, 8000 is default port for FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)