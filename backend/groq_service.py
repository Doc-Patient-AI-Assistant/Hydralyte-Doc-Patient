import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

# ===============================
# LOAD ENV
# ===============================
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ===============================
# LLAMA SUMMARY
# ===============================
def generate_summary(transcript_json: dict) -> dict:
    utterances = transcript_json.get("utterances", [])

    convo = []
    chars = 0
    for u in utterances:
        line = f"{u['speaker']}: {u['text']}\n"
        chars += len(line)
        if chars > 6000:
            break
        convo.append(line)

    conversation = "".join(convo)

    prompt = f"""
You are a medical summarization system.

STRICT RULES:
- Output ONLY valid JSON
- No markdown
- No explanations

JSON FORMAT:
{{
  "doctor_summary": "",
  "symptoms": [],
  "patient_history": [],
  "risk_factors": [],
  "prescription": [],
  "advice": [],
  "recommended_action": ""
}}

Conversation:
{conversation}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    raw = response.choices[0].message.content.strip()

    # ---- HARD JSON EXTRACTION SAFETY NET ----
    try:
        data = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise RuntimeError(f"Invalid LLM output:\n{raw}")
        data = json.loads(match.group())

    return data
