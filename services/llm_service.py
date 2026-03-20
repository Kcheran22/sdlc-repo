from openai import OpenAI
import os
from openai import OpenAI
import os
from dotenv import load_dotenv

# 🔥 ADD THIS LINE
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def clean_requirements(text: str) -> str:
    prompt = f"""
    Convert the following raw inputs into a clean, structured project requirement.

    Content:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content