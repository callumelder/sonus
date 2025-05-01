from typing import Literal
import json
from time import time
from asyncio import Queue
import base64

# Import required modules
from .synthesize import text_to_speech_stream
from .assistant import setup_assistant, setup_gmail_tools, EndConversationTool
from main import handle_workflow_message

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

def create_websocket_aware_transcribe(websocket):
    """
    Creates a transcribe function that uses a specific WebSocket connection.
    
    Args:
        websocket (WebSocket): The WebSocket connection to use for audio streaming
        
    Returns:
        function: A transcribe function that uses the provided WebSocket
    """
    async def websocket_transcribe(state: MessagesState) -> MessagesState:
        """
        Transcribe node that requests audio through the WebSocket connection.
        """
        start = log_state("Transcribe")
        
        # Ensure the websocket has a transcript_queue attribute
        if not hasattr(websocket, 'transcript_queue'):
            websocket.transcript_queue = Queue()
        
        # Signal that we're starting transcription
        await handle_workflow_message(websocket, "start_listening")
        
        # Wait for transcription to complete (filled by SpeechProcessor)
        transcript = await websocket.transcript_queue.get()
        
        # Signal that we're done with transcription
        await handle_workflow_message(websocket, "stop_listening")
        
        log_state("Transcribe", start)
        
        # Return the transcript as a new message
        return {
            "messages": state["messages"] + [transcript]
        }
    
    return websocket_transcribe

def create_websocket_aware_synthesize(websocket):
    """
    Creates a synthesize function that sends audio through a specific WebSocket connection.
    """
    async def websocket_synthesize(state: MessagesState) -> MessagesState:
        start = log_state("Synthesize")
        
        message = state["messages"][-1]
        
        if message.content:
            content = message.content
            # Handle different message content formats
            if isinstance(content, list):
                text = content[0].get('text', '')
            else:
                text = content
                
            if not text:
                log_state("Synthesize", start)
                return state
                
            print(f"[Synthesize] Converting text to speech: {text[:50]}...")
            t0 = time()
            audio_stream = text_to_speech_stream(text)
            print(f"[Synthesize] Text-to-speech conversion took {time() - t0:.2f}s")
            
            # Read the audio data
            audio_data = audio_stream.read()
            
            # Convert to base64 for reliable transmission
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            
            # Send audio data
            audio_size = len(audio_data)
            print(f"[Synthesize] Sending audio to front-end: {audio_size} bytes")
            await handle_workflow_message(
                websocket, 
                "audio_response", 
                {
                    "format": "mp3",
                    "data": encoded_audio,
                    "size": audio_size
                }
            )
            
        log_state("Synthesize", start)
        return state
        
    return websocket_synthesize

class BasicToolNode:
    """A node that runs the tools requested in the last AIMessage."""

    def __init__(self, tools: list, websocket) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}
        self.websocket = websocket

    async def __call__(self, inputs: dict):        
        if messages := inputs.get("messages", []):
            message = messages[-1]
            if hasattr(message, 'content') and message.content:
                if isinstance(message.content, list):
                    transcript = message.content[0].get('text', '')
                else:
                    transcript = message.content
                    
                # Only synthesize if there's text to speak
                if transcript:
                    # Synthesis for intermediate message
                    audio_stream = text_to_speech_stream(transcript)
                    
                    # Read the audio data
                    audio_data = audio_stream.read()
                    
                    # Convert to base64 for reliable transmission
                    encoded_audio = base64.b64encode(audio_data).decode('utf-8')
                    
                    # Send audio data
                    audio_size = len(audio_data)
                    print(f"[Tools] Sending audio to front-end: {audio_size} bytes")
                    await handle_workflow_message(
                        self.websocket, 
                        "audio_response", 
                        {
                            "format": "mp3",
                            "data": encoded_audio,
                            "size": audio_size
                        }
                    )
        else:
            raise ValueError("No message found in input")
        
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

def create_websocket_aware_final_output(websocket):
    async def websocket_aware_final_output(state: MessagesState) -> MessagesState:
        """Handle final message synthesis before ending conversation"""
        print("[Final Output] Processing final message...")
        start = log_state("Final Output")
        
        message = state["messages"][-1]
        if message.content:
            if isinstance(message.content, list):
                text = message.content[0].get('text', '')
            else:
                text = message.content
                
            if not text:
                log_state("Final Output", start)
                return state
                
            print(f"[Final Output] Final text to speak: {text[:50]}...")
            
            print("[Final Output] Converting final text to speech...")
            t0 = time()
            audio_stream = text_to_speech_stream(text)
            print(f"[Final Output] Text-to-speech conversion took {time() - t0:.2f}s")
            
            # Read the audio data
            audio_data = audio_stream.read()
            
            # Convert to base64 for reliable transmission
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            
            # Send audio data
            audio_size = len(audio_data)
            print(f"[Final Output] Sending final audio to front-end: {audio_size} bytes")
            await handle_workflow_message(
                websocket, 
                "audio_response", 
                {
                    "format": "mp3",
                    "data": encoded_audio,
                    "size": audio_size,
                    "isComplete": True
                }
            )
            
        log_state("Final Output", start)
        return state
    return websocket_aware_final_output

def setup_graph_with_websocket(websocket):
    """
    Creates a workflow graph with nodes that can communicate through a WebSocket.
    """
    # Setup tools
    tools = setup_gmail_tools()
    conversation_tool = EndConversationTool()
    all_tools = tools + [conversation_tool]
    assistant = setup_assistant(all_tools)
    
    # Create and compile the graph
    graph_builder = StateGraph(MessagesState)
    tool_node = BasicToolNode(tools=tools, websocket=websocket)
    
    # Create WebSocket-aware functions
    websocket_transcribe = create_websocket_aware_transcribe(websocket)
    websocket_synthesize = create_websocket_aware_synthesize(websocket)
    websocket_final_output = create_websocket_aware_final_output(websocket)
    
    # Nodes
    graph_builder.add_node("chatbot", chatbot(assistant))
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("transcribe", websocket_transcribe)
    graph_builder.add_node("synthesize", websocket_synthesize)
    graph_builder.add_node("final_output", websocket_final_output)
    
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