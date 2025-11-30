# app/utils.py
import os
import re
import openai

# Configura tu API key de OpenAI desde variable de entorno (o hardcodea para pruebas)
openai.api_key = os.getenv("OPENAI_API_KEY", "sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXX")

# Prompts para resumen inteligente
RESUME_PROMPT = {
    "es": "Haz un resumen inteligente en español del siguiente texto:\n",
    "en": "Make a smart summary in English of the following text:\n",
    "pt": "Faça um resumo inteligente em português do seguinte texto:\n",
    "fr": "Fais un résumé intelligent en français du texte suivant:\n",
    "it": "Fai un riassunto intelligente in italiano del seguente testo:\n",
    "de": "Erstelle eine intelligente Zusammenfassung auf Deutsch des folgenden Textes:\n"
}


def formatear_transcripcion(texto: str) -> str:
    """Añade saltos de línea tras punto, exclamación o interrogación."""
    return re.sub(r'([.!?])(\s+)', r'\1\n', texto).strip()


def resumen_inteligente(texto: str, idioma: str) -> str:
    """Genera un resumen usando ChatCompletion."""
    prompt = RESUME_PROMPT.get(idioma, RESUME_PROMPT["es"]) + texto
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=350
    )
    return response.choices[0].message.content.strip()
