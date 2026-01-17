# app/services/whisper.py
# -*- coding: utf-8 -*-
"""
Wrapper de transcripción para PolyScribe.

Función pública:
    transcribe_audio(local_path: str, forced_lang: Optional[str]) -> tuple[str, Optional[str]]

Comportamiento:
  - Usa Whisper (OpenAI) con response_format='verbose_json' para obtener .text y .language.
  - Si forced_lang es None/'auto' → detección automática.
  - Si forced_lang es un ISO-639-1 válido (2 letras) → fuerza ese idioma.
"""

from __future__ import annotations

import os
import re
import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)

try:
    # SDK OpenAI v1.x
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    OpenAI = None  # type: ignore
    log.warning("OpenAI SDK no disponible: %s", e)


# ---------------------- utilidades ---------------------- #
def _normalize_forced_lang(code: Optional[str]) -> Optional[str]:
    """
    Normaliza el código forzado:
      - None / '', 'auto', 'autodetect' => None (auto detección)
      - 'es', 'en', 'pt', ... (2 letras) => tal cual
      - cualquier otra cosa => None (mejor auto)
    """
    if not code:
        return None
    c = (code or "").strip().lower()
    if c in ("", "auto", "autodetect", "automatic"):
        return None
    if re.fullmatch(r"[a-z]{2}", c):
        return c
    return None


# ---------------------- API pública ---------------------- #
def transcribe_audio(local_path: str, forced_lang: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Transcribe un archivo de audio local con Whisper.

    Args:
        local_path: ruta absoluta o relativa del archivo.
        forced_lang: ISO-639-1 (p.ej. 'es', 'en', 'pt') o None para autodetección.

    Returns:
        (transcript, detected_lang)
          transcript: texto de la transcripción (string, puede ser vacío si algo falló).
          detected_lang: código ISO-639-1 detectado por Whisper (o None si no disponible).
    """
    if not local_path or not os.path.exists(local_path):
        raise FileNotFoundError(f"Archivo no encontrado: {local_path}")

    if OpenAI is None:  # pragma: no cover
        raise RuntimeError(
            "OpenAI SDK no disponible. Instala/actualiza 'openai' y verifica OPENAI_API_KEY."
        )

    client = OpenAI()  # Toma OPENAI_API_KEY del entorno
    lang = _normalize_forced_lang(forced_lang)

    # Abrimos el archivo en binario y llamamos al endpoint
    with open(local_path, "rb") as f:
        kwargs = {
            "model": "whisper-1",
            "file": f,
            "response_format": "verbose_json",  # para obtener .language además de .text
        }
        if lang:
            kwargs["language"] = lang

        resp = client.audio.transcriptions.create(**kwargs)

    transcript = getattr(resp, "text", "") or ""
    detected = getattr(resp, "language", None)
    return transcript, detected
