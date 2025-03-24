import openai
import os
from dotenv import find_dotenv, load_dotenv

# reads key-value pairs from .env file and can set them as environment variables
load_dotenv()

client = openai.Client()
model = "gpt-4o-mini"

#== Create Assistant ==#
assistant = client.beta.assistants.create(
    name = "MeowNika",
    instructions="you are a cat master, and you know all the cats in the world. your user will prompt you with cat breeds, and you will respond with a fun fact about that breed.",
    model=model
)

# A Thread represents a conversation between a user and one or many Assistants.
thread = client.beta.threads.create()

# add message to thread
message = client.beta.threads.messages.create(
  thread_id=thread.id,
  role="user",
  content="I want to know about the American Shorthair. Can you help me?"
)

from typing_extensions import override
from openai import AssistantEventHandler
 
# First, we create a EventHandler class to define
# how we want to handle the events in the response stream.
 
class EventHandler(AssistantEventHandler):    
  @override
  def on_text_created(self, text) -> None:
    print(f"\nassistant > ", end="", flush=True)
      
  @override
  def on_text_delta(self, delta, snapshot):
    print(delta.value, end="", flush=True)
      
  def on_tool_call_created(self, tool_call):
    print(f"\nassistant > {tool_call.type}\n", flush=True)
  
  def on_tool_call_delta(self, delta, snapshot):
    if delta.type == 'code_interpreter':
      if delta.code_interpreter.input:
        print(delta.code_interpreter.input, end="", flush=True)
      if delta.code_interpreter.outputs:
        print(f"\n\noutput >", flush=True)
        for output in delta.code_interpreter.outputs:
          if output.type == "logs":
            print(f"\n{output.logs}", flush=True)
 
# Then, we use the `stream` SDK helper 
# with the `EventHandler` class to create the Run 
# and stream the response.
 
with client.beta.threads.runs.stream(
  thread_id=thread.id,
  assistant_id=assistant.id,
  instructions="Please address the user as Nika.",
  event_handler=EventHandler(),
) as stream:
  stream.until_done()

  print(f"\nAssistant ID: {assistant.id}\n")
  print(f"Thread ID: {thread.id}\n")
