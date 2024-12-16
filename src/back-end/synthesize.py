from dotenv import load_dotenv
import os
from typing import IO
from io import BytesIO
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import threading

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("XI_API_KEY")
client = ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
)

def text_to_speech_stream(text: str) -> IO[bytes]:
    # Perform the text-to-speech conversion
    response = client.text_to_speech.convert(
        voice_id="pNInz6obpgDQGcFmaJgB",  # Adam pre-made voice
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_turbo_v2_5",
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

class InterruptiblePlayer:
    def __init__(self):
        self.is_playing = False
        self.should_stop = False
    
    def stop(self):
        """Stop the current playback"""
        self.should_stop = True
        if self.is_playing:
            pygame.mixer.music.stop()
    
    def play_audio_stream(self, audio_stream: IO[bytes]):
        try:
            pygame.mixer.init(frequency=22050)
            
            self.is_playing = True
            self.should_stop = False
            
            pygame.mixer.music.load(audio_stream)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy() and not self.should_stop:
                pygame.time.Clock().tick(10)
                
        finally:
            self.is_playing = False
            pygame.mixer.music.stop()
            pygame.mixer.quit()

# Global player instance that can be accessed to stop playback
audio_player = InterruptiblePlayer()

def play_audio_stream(audio_stream: IO[bytes]):
    """Play audio in a separate thread so it can be interrupted"""
    def play():
        audio_player.play_audio_stream(audio_stream)
    
    playback_thread = threading.Thread(target=play)
    playback_thread.daemon = True  # Thread will be killed when main program exits
    playback_thread.start()

def stop_playback():
    """Stop any currently playing audio"""
    audio_player.stop()