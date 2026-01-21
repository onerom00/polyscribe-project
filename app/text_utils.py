# app/text_utils.py
# -*- coding: utf-8 -*-
"""
Utilidades de limpieza y normalización de texto para transcripciones y resúmenes.

Diseño de las funciones:
- No dependen de librerías externas.
- No hacen "traducción", sólo limpieza y formateo.
- Son conservadoras: prefieren no tocar lo que parece intencional.

Funciones principales:
- clean_transcript(text, lang=''): devuelve una transcripción lista para UI/exports.
- clean_summary(text, lang=''): devuelve un resumen con viñetas uniformes.
"""

from __future__ import annotations
import re
from typing import List

# --- Regex reutilizables
RE_SPACES = re.compile(r"[ \t\u00A0]+")              # espacios + NBSP → un espacio
RE_MULTI_NL = re.compile(r"\n{3,}")                  # 3+ saltos → 2
RE_LINE_TRIM = re.compile(r"[ \t\u00A0]+$", re.M)    # espacios al final de línea
RE_URL = re.compile(r"https?://\S+", re.I)
RE_BULLET_LINE = re.compile(r"^\s*([•\-\–\—\*\·])\s+")
RE_SENTENCE_SPLIT = re.compile(r"(?<=[\.\!\?])\s+(?=[^\s])")
RE_BAD_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,;:\.\!\?\)])")
RE_SPACE_AFTER_PUNCT = re.compile(r"([,;:\.\!\?])([^\s])")

SMART_QUOTES = {
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‚": "'", "‹": "'", "›": "'",
}
DASHES = {
    "–": "-", "—": "-", "−": "-", "-": "-",  # en dash, em dash, minus sign, non-breaking hyphen
}

RTL_LANGS = {"ar", "fa", "he", "ur", "ps"}


def _normalize_quotes_and_dashes(s: str) -> str:
    for k, v in SMART_QUOTES.items():
        if k in s:
            s = s.replace(k, v)
    for k, v in DASHES.items():
        if k in s:
            s = s.replace(k, v)
    return s


def _normalize_spaces(s: str) -> str:
    # normalizar espacios y recortar por línea
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = RE_SPACES.sub(" ", s)
    s = RE_LINE_TRIM.sub("", s)
    s = RE_MULTI_NL.sub("\n\n", s)
    return s.strip()


def _join_soft_linebreaks(s: str) -> str:
    """
    Une líneas que parecen estar partidas a mitad de frase:
    - Si línea A NO termina en [.?!…] y la siguiente empieza en minúscula o dígito → unir.
    - Mantiene saltos dobles (párrafos).
    """
    lines = s.split("\n")
    out: List[str] = []
    buffer = ""

    def is_sentence_end(line: str) -> bool:
        line = line.rstrip()
        return bool(line) and line[-1] in ".?!…:"

    for i, line in enumerate(lines):
        if not buffer:
            buffer = line
            continue

        if buffer.strip() == "":
            out.append(buffer)
            buffer = line
            continue

        # ¿Siguiente línea es continuación?
        stripped = line.lstrip()
        if (not is_sentence_end(buffer)) and stripped[:1].islower():
            buffer = (buffer.rstrip() + " " + stripped)
        else:
            out.append(buffer)
            buffer = line

    if buffer:
        out.append(buffer)

    return "\n".join(out)


def _tidy_punctuation_spaces(s: str) -> str:
    # quitar espacio antes de ,.;:!?)
    s = RE_BAD_SPACE_BEFORE_PUNCT.sub(r"\1", s)
    # asegurar 1 espacio después de ,.;:!? si viene una letra/num
    s = RE_SPACE_AFTER_PUNCT.sub(r"\1 \2", s)
    return s


def _normalize_bullets(s: str) -> str:
    """
    Convierte bullets heterogéneos en "- ", y elimina duplicados de espacios.
    No crea bullets nuevas; sólo normaliza las existentes.
    """
    lines = s.split("\n")
    norm: List[str] = []
    for ln in lines:
        m = RE_BULLET_LINE.match(ln)
        if m:
            rest = ln[m.end():].strip()
            if rest:
                norm.append(f"- {rest}")
            else:
                norm.append("")  # línea sólo con viñeta → elimínala
        else:
            norm.append(ln.rstrip())
    out = "\n".join(norm)
    # evitar viñetas vacías repetidas
    out = re.sub(r"(?:^\s*-\s*$\n?)+", "", out, flags=re.M)
    return out.strip()


def _bulletize_if_paragraph(s: str, lang: str) -> str:
    """
    Si el resumen llegó como un solo párrafo sin bullets, intenta dividir por frases
    y convertir a una lista con "- ".
    """
    text = s.strip()
    if not text:
        return text

    # ¿Ya hay bullets?
    if RE_BULLET_LINE.search(text):
        return _normalize_bullets(text)

    # Si hay múltiples párrafos, respétalos (no forzar bullets).
    if "\n\n" in text:
        return _normalize_bullets(text)

    # Heurística: si hay 3+ frases, bulletizar
    parts = [p.strip() for p in RE_SENTENCE_SPLIT.split(text) if p.strip()]
    if len(parts) >= 3:
        return "\n".join(f"- {p}" for p in parts)
    return text


def clean_transcript(text: str, lang: str = "") -> str:
    """
    Limpieza ligera para transcripción:
    - Unifica comillas/guiones
    - Compacta espacios/saltos
    - Une líneas partidas a mitad de frase
    - Ajusta espacios con puntuación
    NO agrega ni quita contenido sustantivo.
    """
    if not text:
        return ""

    s = text
    s = _normalize_quotes_and_dashes(s)
    s = _normalize_spaces(s)
    s = _join_soft_linebreaks(s)
    s = _tidy_punctuation_spaces(s)
    s = _normalize_spaces(s)
    return s


def clean_summary(text: str, lang: str = "") -> str:
    """
    Limpieza para resumen:
    - Unifica comillas/guiones
    - Compacta espacios/saltos
    - Si no hay bullets y hay suficientes frases, genera bullets "- "
    - Normaliza bullets existentes a "- "
    - Ajusta espacios con puntuación
    """
    if not text:
        return ""

    s = text
    s = _normalize_quotes_and_dashes(s)
    s = _normalize_spaces(s)
    s = _bulletize_if_paragraph(s, lang=lang)
    s = _normalize_bullets(s)
    s = _tidy_punctuation_spaces(s)
    s = _normalize_spaces(s)
    return s
