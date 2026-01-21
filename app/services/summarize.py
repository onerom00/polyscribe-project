# app/services/summarizer.py
# -*- coding: utf-8 -*-
"""
Resumidor central de PolyScribe.

Reglas:
  1) Si target_lang es None (selector neutro) => resume en el MISMO idioma del texto de entrada.
  2) Si target_lang es un código ISO-639-1 (p.ej. 'es', 'en', 'pt') => resume en ese idioma (traduce si hace falta).
  3) Si llega un código inválido => fallback a 'en'.
Además: sin viñetas; devolver un solo párrafo.
"""

from __future__ import annotations

import os
import re
import logging
from typing import Optional

try:
    # SDK OpenAI v1.x
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    OpenAI = None  # type: ignore
    logging.getLogger(__name__).warning("OpenAI SDK no disponible: %s", e)

log = logging.getLogger(__name__)

# Modelo por defecto (puedes sobreescribir con variable de entorno)
DEFAULT_SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")


# ---------------------- utilidades ---------------------- #
_BULLET_RX = re.compile(r"^\s*([•\-–—*]|\d+\.)\s*", re.MULTILINE)

def _sanitize_to_single_paragraph(text: str) -> str:
    """
    Quita viñetas si el modelo se “emociona”, y fuerza un solo párrafo.
    """
    if not text:
        return ""
    # eliminar marcas de viñetas al inicio de línea
    txt = _BULLET_RX.sub("", text)
    # colapsar saltos de línea múltiples a un espacio
    txt = " ".join(line.strip() for line in txt.splitlines() if line.strip())
    # limpiar espacios extra
    return re.sub(r"\s+", " ", txt).strip()


def _normalize_lang(code: Optional[str]) -> Optional[str]:
    """
    Normaliza el código de idioma (ISO-639-1). Devuelve None para 'auto' y equivalentes.
    """
    if not code:
        return None
    c = (code or "").strip().lower()
    if c in ("", "auto", "autodetect", "same", "match", "igual", "mismo"):
        return None
    # aceptar solo 2 letras [a-z]
    if re.fullmatch(r"[a-z]{2}", c):
        return c
    return "en"  # fallback seguro


def _system_prompt(target_lang: Optional[str]) -> str:
    """
    Construye el prompt de sistema evitando sesgos de idioma.
    - Sin target_lang => instrucción neutra EN INGLÉS para que use el MISMO idioma del texto de entrada.
    - Con target_lang => instrucción para usar ese idioma.
    """
    code = _normalize_lang(target_lang)
    if not code:
        return (
            "You are an assistant that summarizes the user's text in the SAME language as the input text. "
            "Automatically detect the language from the content. "
            "Return a single concise paragraph. Do not use bullet points."
        )
    # code validado (2 letras) o 'en' por fallback
    return (
        f"You are an assistant that summarizes the user's text in '{code}'. "
        f"Return a single concise paragraph. Do not use bullet points."
    )


# ---------------------- API pública ---------------------- #
def summarize_text(
    text: str,
    target_lang: Optional[str] = None,
    *,
    model: Optional[str] = None,
    temperature: float = 0.15,
) -> str:
    """
    Resume 'text' cumpliendo las reglas especificadas arriba.
    - target_lang: None => MISMO idioma del texto; 'es'/'en'/'pt'/etc => fuerza idioma.
    - model: sobreescribe el modelo por defecto.
    - temperature: baja para consistencia.

    Devuelve: string con un solo párrafo, sin viñetas.
    """
    if not text or not text.strip():
        return ""

    if OpenAI is None:  # pragma: no cover
        raise RuntimeError("OpenAI SDK no disponible. Verifica la instalación del paquete 'openai'.")

    client = OpenAI()  # toma OPENAI_API_KEY del entorno
    use_model = (model or DEFAULT_SUMMARY_MODEL).strip()

    sys_msg = _system_prompt(target_lang)

    # Llamada a Chat Completions
    resp = client.chat.completions.create(
        model=use_model,
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": text},
        ],
        temperature=float(temperature),
    )

    raw = (resp.choices[0].message.content or "").strip()
    return _sanitize_to_single_paragraph(raw)


# ---------------------- helper opcional para rutas ---------------------- #
def summarize_for_job_text(text: str, summary_lang: Optional[str]) -> str:
    """
    Wrapper fino pensado para usar desde rutas/servicios del job:
        - summary_lang llega de la UI/DB (puede ser 'auto', '', None, 'es', 'en', etc.)
        - devuelve siempre 1 párrafo sin bullets.
    """
    try:
        return summarize_text(text, target_lang=summary_lang)
    except Exception as e:
        log.exception("Fallo al resumir: %s", e)
        # no explotar el job por el resumen; devolver vacío y que la UI lo refleje
        return ""
