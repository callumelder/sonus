from dotenv import load_dotenv

from transcribe import MicrophoneStream, listen_print_loop
from synthesize import text_to_speech_stream, play_audio_stream
from authenticate import get_token

from google.cloud import speech

from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_google_community import GmailToolkit
from langchain_google_community.gmail.utils import build_resource_service, get_gmail_credentials

from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START


load_dotenv()

    
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

def chatbot(state: MessagesState) -> MessagesState:
    print(state["messages"])
    response = llm_with_tools.invoke(state["messages"])
    print(f"Response: {response}")
    
    return {
        "messages": [response]
    }
    
def tools_condition(state: MessagesState) -> Literal["tools", "synthesize"]:
    """Return either 'tools' or 'synthesize' as the next node"""
    latest_message = state["messages"][-1]
    
    if latest_message.tool_calls:
        return "tools"
    return "synthesize"

    
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
    llm_with_tools = llm.bind_tools(tools)
    
    # Create and compile the graph
    graph_builder = StateGraph(MessagesState)
    tool_node = ToolNode(tools=tools)
    
    # Nodes
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("transcribe", transcribe)
    graph_builder.add_node("synthesize", synthesize)
    
    # Edges
    graph_builder.add_edge(START, "transcribe")
    graph_builder.add_edge("transcribe", "chatbot")
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_edge("synthesize", "transcribe")
    # graph_builder.add_edge("chatbot", END)
    
    # Conditional Edges
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition
    )
    
    graph = graph_builder.compile()

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
    
    print("Ready")
    state = MessagesState(messages=[])
    state = graph.invoke(state)