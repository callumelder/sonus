import asyncio
import json
import logging
from typing import Optional
from queue import Queue, Empty
from threading import Thread, Event
import traceback

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import speech
from langgraph.graph import MessagesState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SpeechProcessor:
    def __init__(self, websocket: WebSocket):
        self.client = speech.SpeechClient()
        self.websocket = websocket
        self.streaming_config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US",
                enable_automatic_punctuation=True,
            ),
            interim_results=True,
        )
        self.audio_queue = Queue()
        self.is_streaming = False
        self.stop_event = Event()
        self.streaming_thread = None
        self.transcript_queue = getattr(websocket, 'transcript_queue', None)

    async def start(self):
        """Starts the streaming process."""
        if not self.is_streaming:
            self.is_streaming = True
            self.stop_event.clear()
            self.streaming_thread = Thread(target=self._run_streaming)
            self.streaming_thread.daemon = True
            self.streaming_thread.start()
            logger.info("Streaming thread started")

    def _run_streaming(self):
        """Runs the streaming recognition in a separate thread."""
        try:
            logger.info("Starting streaming recognition")

            def audio_generator():
                while not self.stop_event.is_set():
                    try:
                        chunk = self.audio_queue.get(timeout=0.5)
                        if chunk is None:  # Sentinel value
                            break
                        yield speech.StreamingRecognizeRequest(audio_content=chunk)
                    except Empty:
                        continue
                logger.info("Audio generator ending")

            responses = self.client.streaming_recognize(
                self.streaming_config,
                audio_generator()
            )

            for response in responses:
                if self.stop_event.is_set():
                    break
                    
                if not response.results:
                    continue

                result = response.results[0]
                if not result.alternatives:
                    continue

                transcript = result.alternatives[0].transcript
                is_final = result.is_final

                # Send transcript back to client
                asyncio.run(self._send_transcript(transcript, is_final))

        except Exception as e:
            logger.error(f"Error in streaming thread: {traceback.format_exc()}")
        finally:
            self.is_streaming = False
            logger.info("Streaming thread ended")

    async def _send_transcript(self, transcript: str, is_final: bool):
        """Sends transcript back to the client and to the workflow if final."""
        try:
            await self.websocket.send_json({
                "type": "final_transcript" if is_final else "interim_transcript",
                "text": transcript
            })
            
            # If this is a final transcript and we're in workflow mode, put it in the queue
            if is_final and self.transcript_queue:
                await self.transcript_queue.put(transcript)
                
        except Exception as e:
            logger.error(f"Error sending transcript: {e}")

    async def add_chunk(self, chunk: bytes):
        """Adds an audio chunk to the processing queue."""
        if self.is_streaming:
            # chunk_size = len(chunk)
            # logger.debug(f"Adding chunk of size {chunk_size} to queue")
            self.audio_queue.put(chunk)

    async def stop(self):
        """Stops the streaming process."""
        logger.info("Stopping speech processor...")
        self.stop_event.set()
        self.is_streaming = False
        self.audio_queue.put(None)  # Sentinel value to stop the generator
        
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=2.0)
        logger.info("Speech processor stopped")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("New WebSocket connection attempt")
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    # Create a workflow instance for this connection
    workflow = create_workflow_for_connection(websocket)
    
    # Initialize SpeechProcessor once at connection time
    speech_processor = SpeechProcessor(websocket)
    # Create a transcript queue for this connection and attach it to the websocket
    websocket.transcript_queue = asyncio.Queue()
    speech_processor.transcript_queue = websocket.transcript_queue
    
    # Start the speech processor immediately
    await speech_processor.start()
    logger.info("Speech processor started")
    
    try:
        # Initialize workflow state
        state = MessagesState(messages=[])
        
        while True:
            try:
                data = await websocket.receive_json()
                
                if data["type"] == "start_conversation":
                    logger.info("Starting conversation workflow")
                    # Start a new conversation workflow
                    # This runs asynchronously since the workflow will trigger
                    # the transcribe node which will request audio
                    asyncio.create_task(workflow.ainvoke(state))
                
                elif data["type"] == "audio_data":
                    chunk = bytes(data["chunk"])
                    
                    # Just ensure it's still streaming
                    if not speech_processor.is_streaming:
                        logger.debug("Restarting speech processor")
                        await speech_processor.start()
                    
                    await speech_processor.add_chunk(chunk)
                    
                elif data["type"] == "stop":
                    logger.info("Received stop signal")
                    break
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
            except Exception as e:
                logger.error(f"Error processing message: {traceback.format_exc()}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {traceback.format_exc()}")
    finally:
        logger.info("Cleaning up resources")
        if speech_processor:
            await speech_processor.stop()
        logger.info("WebSocket connection closed")
        
def create_workflow_for_connection(websocket):
    """
    Creates a LangGraph workflow instance tied to a specific WebSocket connection.
    This allows the workflow to communicate through this WebSocket.
    
    Args:
        websocket (WebSocket): The active WebSocket connection
        
    Returns:
        StateGraph: A compiled workflow graph with WebSocket-aware nodes
    """
    # Import the workflow setup function
    from model.workflow import setup_graph_with_websocket
    
    # Create and return a workflow graph that's aware of this WebSocket
    return setup_graph_with_websocket(websocket)

# Function to handle messages between workflow and WebSocket
async def handle_workflow_message(websocket, message_type, data=None):
    """
    Routes messages between the workflow and the WebSocket client.
    
    Args:
        websocket (WebSocket): The active WebSocket connection
        message_type (str): Type of message (e.g., "start_listening", "stop_listening")
        data (dict, optional): Additional data to send with the message
    """
    message = {
        "type": message_type
    }
    
    if data:
        message.update(data)
    
    try:
        # Handle large audio data efficiently
        if message_type == "audio_response" and "data" in message:
            # Log the size but not the full data
            data_size = len(message["data"]) if isinstance(message["data"], (str, bytes, list)) else "unknown"
            logger.info(f"Sending audio data of size: {data_size}")
        else:
            logger.info(f"Sending message: {message_type}")
            
        await websocket.send_json(message)
    except Exception as e:
        logger.error(f"Error sending message via WebSocket: {str(e)}")

# Function to request audio streaming from the client
async def request_audio_from_client(websocket):
    """
    Sends a command to the client to start streaming audio.
    
    Args:
        websocket (WebSocket): The active WebSocket connection
    """
    await handle_workflow_message(websocket, "start_listening")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")