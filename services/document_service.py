from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_brd(cleaned_requirement: str) -> str:
    prompt = f"""
    Generate a Business Requirement Document (BRD) based on the following:

    {cleaned_requirement}

    Include:
    - Project Overview
    - Objectives
    - Stakeholders
    - Scope
    - Business Requirements
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


def generate_frd(cleaned_requirement: str) -> str:
    prompt = f"""
    Generate a Functional Requirement Document (FRD) based on the following:

    {cleaned_requirement}

    Include:
    - System Overview
    - Functional Requirements
    - User Flows
    - API Requirements
    - Data Flow
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content