# from openai import OpenAI
# import os
# from openai import OpenAI
# import os
# from dotenv import load_dotenv

# # 🔥 ADD THIS LINE
# load_dotenv()

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# def transcribe_audio(file_path: str) -> str:
#     with open(file_path, "rb") as audio:
#         response = client.audio.transcriptions.create(
#             model="gpt-4o-mini-transcribe",
#             file=audio
#         )
#     return response.text

import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.assemblyai.com/v2"

headers = {
    "authorization": os.getenv("ASSEMBLY_API_KEY")
}


def transcribe_audio(file_path: str) -> str:
    # 1. Upload file
    with open(file_path, "rb") as f:
        upload_res = requests.post(
            f"{BASE_URL}/upload",
            headers=headers,
            data=f
        )
    upload_res.raise_for_status()
    audio_url = upload_res.json()["upload_url"]

    # 2. Start transcription
    transcript_res = requests.post(
        f"{BASE_URL}/transcript",
        json={"audio_url": audio_url},
        headers={**headers, "content-type": "application/json"}
    )
    transcript_res.raise_for_status()
    transcript_id = transcript_res.json()["id"]

    # 3. Poll for result
    while True:
        result = requests.get(
            f"{BASE_URL}/transcript/{transcript_id}",
            headers=headers
        ).json()

        status = result["status"]
        print("STATUS:", status)

        if status == "completed":
            return result["text"]

        if status == "error":
            raise Exception(result.get("error"))

        time.sleep(3)