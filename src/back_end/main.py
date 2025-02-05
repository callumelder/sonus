from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import speech
import asyncio
import json
import logging
from typing import Optional
from queue import Queue
from threading import Thread, Event
import traceback

logging.basicConfig(level=logging.DEBUG)
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
                    except Queue.Empty:
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
        """Sends transcript back to the client."""
        try:
            await self.websocket.send_json({
                "type": "final_transcript" if is_final else "interim_transcript",
                "text": transcript
            })
        except Exception as e:
            logger.error(f"Error sending transcript: {e}")

    async def add_chunk(self, chunk: bytes):
        """Adds an audio chunk to the processing queue."""
        if self.is_streaming:
            chunk_size = len(chunk)
            logger.debug(f"Adding chunk of size {chunk_size} to queue")
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
    
    speech_processor = SpeechProcessor(websocket)
    
    try:
        await speech_processor.start()
        
        while True:
            try:
                data = await websocket.receive_json()
                
                if data["type"] == "audio_data":
                    chunk = bytes(data["chunk"])
                    chunk_size = len(chunk)
                    logger.debug(f"Received audio chunk: {chunk_size} bytes")
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
        await speech_processor.stop()
        logger.info("WebSocket connection closed")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")