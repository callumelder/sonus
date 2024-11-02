import requests
from dotenv import load_dotenv
import os

load_dotenv()

xi_api_key = os.getenv("XI_API_KEY")

CHUNK_SIZE = 1024

# George voice"
url = f"https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb"

headers = {
  "Accept": "audio/mpeg",
  "Content-Type": "application/json",
  "xi-api-key": xi_api_key
}

text_sample = """
Hi Sarah,

I have been adding Roozbeh to the discussion via Cc, please stop replying just to me and include him so he can reply directly to you.

However, he has said he will be driving (car rego is 274EA8), he'd like tea for his beverage and his dietary restrictions is no pork.

Thanks,
Callum
"""

data = {
  "text": text_sample,
  "model_id": "eleven_monolingual_v1",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.5
  }
}

response = requests.post(url, json=data, headers=headers)
with open('output.mp3', 'wb') as f:
    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
        if chunk:
            f.write(chunk)
