from typing import Literal
import json
from time import time

# Utilities
from transcribe import MicrophoneStream
from synthesize import text_to_speech_stream, play_audio_stream, stop_playback
from assistant import setup_assistant, setup_gmail_tools

from google.cloud import speech
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.messages import ToolMessage


def log_state(state_name: str, start_time: float = None):
    if start_time:
        duration = time() - start_time
        print(f"[{state_name}] Completed in {duration:.2f}s")
    else:
        print(f"[{state_name}] Starting...")
        return time()
    
def chatbot(assistant_instance):
    def chatbot_node(state: MessagesState) -> MessagesState:
        print("[Chatbot] Processing message...")
        print(f"[Chatbot] Input state messages: {state['messages']}")
        start = log_state("Chatbot")
        result = assistant_instance(state)
        print(f"[Chatbot] Output result: {result}")
        log_state("Chatbot", start)
        return result
    return chatbot_node

def transcribe(state: MessagesState) -> MessagesState:
    start = log_state("Transcribe")
    with MicrophoneStream() as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )
        
        responses = client.streaming_recognize(streaming_config, requests)
        
        # Stop playback as soon as we get ANY results, even interim ones
        first_speech_detected = False
        transcript = ""
        
        for response in responses:
            # print(f"Got response: {response}")  # Debug log
            if response.results:
                # If this is the first detection of speech, stop playback immediately
                if not first_speech_detected:
                    print("First speech detected! Stopping playback...")  # Debug log
                    stop_playback()
                    first_speech_detected = True
                
                # Wait for a final result to get the full transcript
                result = response.results[0]
                if result.is_final:
                    transcript = result.alternatives[0].transcript
                    print(f"Final transcript: {transcript}")  # Debug log
                    break
                # else:
                    # print(f"Interim transcript: {result.alternatives[0].transcript}")  # Debug log
                    
        log_state("Transcribe", start)
        return {
            "messages": state["messages"] + [transcript]
        }

def synthesize(state: MessagesState) -> MessagesState:
    start = log_state("Synthesize")
    message = state["messages"][-1]
    if message.content:
        print("[Synthesize] Converting text to speech...")
        t0 = time()
        audio_stream = text_to_speech_stream(message.content)
        print(f"[Synthesize] Text-to-speech conversion took {time() - t0:.2f}s")
        
        print("[Synthesize] Starting playback...")
        play_audio_stream(audio_stream)
    log_state("Synthesize", start)
    return state
    
def should_continue(state: MessagesState) -> Literal["chatbot", "end"]:
    """Determine if the conversation should continue or end"""
    latest_message = state["messages"][-1]
    
    if "goodbye" in latest_message:
        print("ENDING CONVERSATION")
        return "end"
    return "chatbot"

class BasicToolNode:
    """A node that runs the tools requested in the last AIMessage."""

    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    def __call__(self, inputs: dict):
        if messages := inputs.get("messages", []):
            message = messages[-1]
            transcript = message.content[0]['text']
        else:
            raise ValueError("No message found in input")
        
        # Synthesis
        audio_stream = text_to_speech_stream(transcript)
        play_audio_stream(audio_stream)
        
        # Tool Call
        outputs = []
        for tool_call in message.tool_calls:
            tool_result = self.tools_by_name[tool_call["name"]].invoke(
                tool_call["args"]
            )
            outputs.append(
                ToolMessage(
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        return {"messages": outputs}
    
def tools_condition(state: MessagesState) -> Literal["tools", "synthesize"]:
    print("[Router] Checking message for tool calls...")
    latest_message = state["messages"][-1]
    print(f"[Router] Latest message type: {type(latest_message)}")
    print(f"[Router] Latest message content: {latest_message}")
    
    has_tools = hasattr(latest_message, 'tool_calls') and latest_message.tool_calls
    print(f"[Router] Has tool calls: {has_tools}")
    
    result = "tools" if has_tools else "synthesize"
    print(f"[Router] Routing to: {result}")
    return result

def setup_graph():    
    tools = setup_gmail_tools()
    assistant = setup_assistant(tools)
    
    # Create and compile the graph
    graph_builder = StateGraph(MessagesState)
    tool_node = BasicToolNode(tools=tools)
    
    # Nodes
    graph_builder.add_node("chatbot", chatbot(assistant))
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
    
    graph_builder.add_conditional_edges(
        "transcribe",
        should_continue,
        {
            "chatbot": "chatbot",
            "end": END
        }
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