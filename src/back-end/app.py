from dotenv import load_dotenv

from transcribe import MicrophoneStream, listen_print_loop
from synthesize import text_to_speech_stream, play_audio_stream

from google.cloud import speech

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI

from langchain_core.messages import HumanMessage, AIMessage


load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]
    
llm = ChatOpenAI(model="gpt-4o")

client = speech.SpeechClient()
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000,
    language_code="en-US",
)
streaming_config = speech.StreamingRecognitionConfig(
    config=config, interim_results=True
)


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

# Create and compile the graph
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()


state = State(messages=[])
while True:
    state = graph.invoke(state)