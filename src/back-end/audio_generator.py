import sounddevice as sd
from scipy.io.wavfile import write

# Settings
duration = 5  # Duration of recording in seconds
sample_rate = 44100  # Sample rate (CD quality)

# Recording
print("Recording...")
audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
sd.wait()  # Wait until recording is finished
print("Recording complete.")

# Save as .wav file
file_name = 'output.wav'
write(file_name, sample_rate, audio_data)
print(f"Audio saved as '{file_name}'")
