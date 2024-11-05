from dotenv import load_dotenv

from transcribe import MicrophoneStream, listen_print_loop
from synthesize import text_to_speech_stream, play_audio_stream
from authenticate import get_token

from google.cloud import speech

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI

from langchain_core.messages import HumanMessage, AIMessage

from langgraph.prebuilt import create_react_agent
from langchain_google_community import GmailToolkit
from langchain_google_community.gmail.utils import (
    build_resource_service,
    get_gmail_credentials,
)

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]

def chatbot(state: State) -> State:    
    # 1. Speech to text
    with MicrophoneStream() as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )
        responses = client.streaming_recognize(streaming_config, requests)
        transcribed_text = listen_print_loop(responses)
    
    # 2. LLM interaction
    state["messages"].append(HumanMessage(content=transcribed_text))
    response = llm.invoke(state["messages"])
    print(f"AI Message: {response}")
    state["messages"].append(AIMessage(content=response.content))
    
    # 3. Text to speech
    audio_stream = text_to_speech_stream(response.content)
    play_audio_stream(audio_stream)
    
    return state

    
if __name__ == "__main__":
    # Setup gmail credentials
    # Define the required scopes (in this case, for Gmail read, compose, send, and modify)
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    get_token(SCOPES)
        
    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=SCOPES,
        client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    toolkit = GmailToolkit(api_resource=api_resource)
        
    gmail_tools = toolkit.get_tools()
    tools = [tool for tool in gmail_tools]
    llm = ChatOpenAI(model="gpt-4o")
    
    # Create and compile the graph
    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", END)
    graph = graph_builder.compile()

    # Setup speech client
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )
    
    state = State(messages=[])
    while True:
        state = graph.invoke(state)