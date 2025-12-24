import os
from dotenv import load_dotenv
from groq import Groq

# ================= LOAD ENV =================
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ================= TEXT TRANSLATION =================
def translate_text(text: str, target_lang: str) -> str:
    """
    Translate medical text into target language.

    target_lang examples:
    - en : English
    - hi : Hindi
    - mr : Marathi
    - gu : Gujarati
    - ta : Tamil
    - te : Telugu
    - kn : Kannada
    - ml : Malayalam
    - bn : Bengali

    NOTE:
    - Used ONLY after medical summarization
    - Keys are NEVER translated, only values
    """

    if not text or not text.strip():
        return text

    prompt = f"""
Translate the following medical text into {target_lang}.

STRICT RULES:
- Preserve medical terminology
- Do NOT summarize
- Do NOT explain
- Do NOT add extra words
- Output ONLY the translated text

Text:
{text}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a medical translation engine."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )

    return response.choices[0].message.content.strip()
