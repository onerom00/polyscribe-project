# app/services/translate.py
import os
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def translate_text(text: str, to_lang: str) -> str:
    if not text or not to_lang:
        return text
    system = "You are a precise translator. Preserve meaning, tone and proper nouns."
    user = f"Translate to {to_lang}. Output only the translation, no explanations.\n\nText:\n{text}"
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.1,
        max_tokens=2000
    )
    return (r.choices[0].message.content or "").strip()
