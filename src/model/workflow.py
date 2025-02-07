from typing import Literal
import json
from time import time

from transcribe import MicrophoneStream
from synthesize import text_to_speech_stream, play_audio_stream
from assistant import setup_assistant, setup_gmail_tools, EndConversationTool

from google.cloud import speech
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
        
        transcript = ""
        for response in responses:
            if response.results:
                # Wait for a final result to get the full transcript
                result = response.results[0]
                if result.is_final:
                    transcript = result.alternatives[0].transcript
                    print(f"Final transcript: {transcript}")
                    break
                    
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
    
def tools_condition(state: MessagesState) -> Literal["tools", "synthesize", "final_output"]:
    """Route to tools, synthesize, or final output based on message content"""
    print("[Router] Checking message for tool calls...")
    latest_message = state["messages"][-1]
    print(f"[Router] Latest message type: {type(latest_message)}")
    print(f"[Router] Latest message content: {latest_message}")
    
    if hasattr(latest_message, 'tool_calls') and latest_message.tool_calls:
        # Check if end_conversation tool was called
        for tool_call in latest_message.tool_calls:
            if tool_call["name"] == "end_conversation":
                print("[Router] End conversation tool called, routing to final output")
                return "final_output"
        print("[Router] Tool calls present, routing to tools")
        return "tools"
    
    print("[Router] No tool calls, routing to synthesize")
    return "synthesize"

def final_output(state: MessagesState) -> MessagesState:
    """Handle final message synthesis before ending conversation"""
    print("[Final Output] Processing final message...")
    start = log_state("Final Output")
    
    message = state["messages"][-1]
    if message.content and isinstance(message.content, list) and message.content[0].get('text'):
        text = message.content[0]['text']
        print(f"Final text to speak: {text}")
        
        print("[Final Output] Converting final text to speech...")
        t0 = time()
        audio_stream = text_to_speech_stream(text)
        print(f"[Final Output] Text-to-speech conversion took {time() - t0:.2f}s")
        
        print("[Final Output] Starting final playback...")
        play_audio_stream(audio_stream)
        
    log_state("Final Output", start)
    return state

def setup_graph():
    # Setup tools
    tools = setup_gmail_tools()
    conversation_tool = EndConversationTool()
    all_tools = tools + [conversation_tool]
    assistant = setup_assistant(all_tools)
    
    # Create and compile the graph
    graph_builder = StateGraph(MessagesState)
    tool_node = BasicToolNode(tools=tools)
    
    # Nodes
    graph_builder.add_node("chatbot", chatbot(assistant))
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("transcribe", transcribe)
    graph_builder.add_node("synthesize", synthesize)
    graph_builder.add_node("final_output", final_output)
    
    # Edges
    graph_builder.add_edge(START, "transcribe")
    graph_builder.add_edge("transcribe", "chatbot")
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_edge("synthesize", "transcribe")
    graph_builder.add_edge("final_output", END)
    
    # Conditional Edges
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
        {
            "tools": "tools",
            "synthesize": "synthesize",
            "final_output": "final_output"
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
    state = MessagesState(messages=[])
    state = graph.invoke(state)