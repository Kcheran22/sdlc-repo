from openai import OpenAI
import os
from openai import OpenAI
import os
from dotenv import load_dotenv

# 🔥 ADD THIS LINE
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def transcribe_audio(file_path: str) -> str:
    with open(file_path, "rb") as audio:
        response = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio
        )
    return response.text