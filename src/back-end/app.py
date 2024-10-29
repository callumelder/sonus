import asyncio
import websockets
import base64
import numpy as np
import wave
import os
import json

# Converts Float32Array to PCM16 data
def float_to_16bit_pcm(float32_array):
    pcm16_array = np.clip(float32_array, -1, 1)
    pcm16_array = (pcm16_array * 32767).astype(np.int16)
    return pcm16_array.tobytes()

# Converts a Float32Array to base64-encoded PCM16 data
def base64_encode_audio(float32_array):
    pcm_data = float_to_16bit_pcm(float32_array)
    return base64.b64encode(pcm_data).decode('utf-8')

# Load and process the audio file (assumes mono .wav file)
def process_audio(file_path):
    try:
        with wave.open(file_path, 'rb') as wf:
            assert wf.getnchannels() == 1  # Ensure mono audio
            assert wf.getsampwidth() == 2  # Ensure PCM16 format
            frames = wf.readframes(wf.getnframes())
            float32_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767
            return base64_encode_audio(float32_array)
    except Exception as e:
        print(f'Error processing audio: {e}')
        return None

# Establish WebSocket connection with OpenAI API
async def connect_to_openai():
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "OpenAI-Beta": "realtime=v1",
    }

    async with websockets.connect(url, extra_headers=headers) as ws:
        print("Connected to server.")

        # Process the audio file
        base64_audio_data = process_audio('./output.wav')

        if base64_audio_data:
            # Create and send the audio input event
            audio_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "audio": base64_audio_data
                        }
                    ]
                }
            }
            await ws.send(json.dumps(audio_event))
        else:
            print('Failed to process audio file.')

        # Create and send the text-based response request
        text_event = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": "Please assist the user.",
            }
        }
        await ws.send(json.dumps(text_event))

        try:
            async for message in ws:
                print('Received:', message)
        except websockets.exceptions.ConnectionClosed as e:
            print('Disconnected from server:', e)

# Start the connection
asyncio.run(connect_to_openai())
