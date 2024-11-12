from typing import Literal
from google.cloud import speech
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START
from transcribe import MicrophoneStream, listen_print_loop
from synthesize import text_to_speech_stream, play_audio_stream
from authenticate import get_token
from assistant import setup_assistant, setup_gmail_tools

def transcribe(state: MessagesState) -> MessagesState:
    with MicrophoneStream() as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )
        responses = client.streaming_recognize(streaming_config, requests)
        transcribed_text = listen_print_loop(responses)
        
    return {
        "messages": [transcribed_text]
    }

def synthesize(state: MessagesState) -> MessagesState:
    message = state["messages"][-1]
    if message.content:
        print("synthesize")
        # audio_stream = text_to_speech_stream(message.content)
        # play_audio_stream(audio_stream)
    
    return {
        "messages": []
    }
    
def tools_condition(state: MessagesState) -> Literal["tools", "synthesize"]:
    """Return either 'tools' or 'synthesize' as the next node"""
    latest_message = state["messages"][-1]
    
    if latest_message.tool_calls:
        return "tools"
    return "synthesize"

def setup_graph():
    # Setup gmail credentials and assistant
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    get_token(SCOPES)
    
    tools = setup_gmail_tools()
    assistant  = setup_assistant(tools)
    
    # Create and compile the graph
    graph_builder = StateGraph(MessagesState)
    tool_node = ToolNode(tools=tools)
    
    # Nodes
    graph_builder.add_node("chatbot", assistant)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("transcribe", transcribe)
    graph_builder.add_node("synthesize", synthesize)
    
    # Edges
    graph_builder.add_edge(START, "transcribe")
    graph_builder.add_edge("transcribe", "chatbot")
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_edge("synthesize", "transcribe")
    
    # Conditional Edges
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition
    )
    
    return graph_builder.compile()

if __name__ == "__main__":
    # Setup speech client
    client = speech.SpeechClient()
    recognition_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=recognition_config, interim_results=True
    )
    
    # Setup and run the graph
    graph = setup_graph()
    print("Ready")
    state = MessagesState(messages=[])
    state = graph.invoke(state)