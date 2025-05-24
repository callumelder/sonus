from dotenv import load_dotenv
import os
from typing import IO, Union
from io import BytesIO

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame


load_dotenv()

ELEVENLABS_API_KEY = os.getenv("XI_API_KEY")
client = ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
)

def text_to_speech_stream(text: str) -> BytesIO:
    """
    Convert text to speech and return a BytesIO object containing MP3 audio data.
    
    Args:
        text: The text to convert to speech
        
    Returns:
        BytesIO: A stream containing the audio data
    """
    # Perform the text-to-speech conversion
    response = client.text_to_speech.convert(
        voice_id="nPczCjzI2devNBz1zQrb",  # Brian pre-made voice
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_turbo_v2_5",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=False,
        ),
    )

    # Create a BytesIO object to hold the audio data in memory
    audio_stream = BytesIO()

    # Write each chunk of audio data to the stream
    for chunk in response:
        if chunk:
            audio_stream.write(chunk)

    # Reset stream position to the beginning
    audio_stream.seek(0)
    return audio_stream