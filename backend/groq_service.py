import os
import json
from dotenv import load_dotenv
from groq import Groq

# ===============================
# LOAD ENV
# ===============================
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ===============================
# SAFE JSON EXTRACTOR
# ===============================
def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise RuntimeError(f"Invalid LLM output:\n{text}")

    snippet = text[start:end + 1]
    return json.loads(snippet)

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

    # 🧪 DEBUG VISIBILITY (optional but extremely useful)
    print("\n🧠 RAW LLM OUTPUT:\n", raw, "\n", flush=True)

    # ===============================
    # BULLETPROOF JSON PARSING
    # ===============================
    try:
        data = json.loads(raw)
    except Exception:
        data = extract_json(raw)

    return data
