from dotenv import load_dotenv
import os
from typing import IO
from io import BytesIO
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import pygame

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("XI_API_KEY")
client = ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
)

text = """
This is a sample text for audio streaming
"""

def text_to_speech_stream(text: str) -> IO[bytes]:
    # Perform the text-to-speech conversion
    response = client.text_to_speech.convert(
        voice_id="pNInz6obpgDQGcFmaJgB",  # Adam pre-made voice
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=True,
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

def play_audio_stream(audio_stream: IO[bytes]):
    # Initialize pygame mixer
    pygame.mixer.init(frequency=22050)
    
    try:
        # Load the audio stream
        pygame.mixer.music.load(audio_stream)
        
        # Play the audio
        pygame.mixer.music.play()
        
        # Wait for the audio to finish
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
    finally:
        # Clean up
        pygame.mixer.quit()

if __name__ == "__main__":
    # Get the audio stream
    audio_stream = text_to_speech_stream(text)
    
    # Play the audio
    play_audio_stream(audio_stream)