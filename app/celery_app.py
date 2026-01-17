# app/celery_app.py
# -*- coding: utf-8 -*-
import os
import io
import json
import time
import logging
from datetime import datetime

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from celery import Celery
from dotenv import load_dotenv

from app.database import SessionLocal
from app.models import AudioJob, UsageLedger

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# Celery (EAGER por defecto si no hay broker)
# -----------------------------------------------------------------------------
_broker = os.getenv("CELERY_BROKER_URL", "memory://")
_backend = os.getenv("CELERY_RESULT_BACKEND")

celery_app = Celery("polyscribe", broker=_broker, backend=_backend)

if _broker.startswith("memory"):
    # Ejecuta en el mismo proceso Flask (desarrollo)
    celery_app.conf.update(task_always_eager=True, task_ignore_result=True)
    logger.info("[celery] EAGER mode ON (memory broker): tasks run in Flask process")
else:
    logger.info("[celery] BROKER=%s BACKEND=%s", _broker, _backend)

# -----------------------------------------------------------------------------
# OpenAI: creación perezosa del cliente
# -----------------------------------------------------------------------------
_openai_client = None

def _get_openai():
    """
    Crea el cliente OpenAI cuando realmente se necesita (evita fallos por
    cargar .env después del import).
    """
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    # Intenta cargar .env si aún no se cargó
    if not os.getenv("OPENAI_API_KEY"):
        load_dotenv(override=False)

    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no está configurado.")

    _openai_client = OpenAI(api_key=api_key)
    return _openai_client


# -----------------------------------------------------------------------------
# Utilidades DB
# -----------------------------------------------------------------------------
def _db_get_job(db, job_id: int):
    return db.get(AudioJob, job_id)

def _job_set_status(db, job: AudioJob, status: str, error: str | None = None):
    job.status = status
    if error:
        job.error = error
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)

def _save_transcript_and_summary(
    db,
    job: AudioJob,
    transcript: str,
    language: str,
    summary_text: str | None
):
    job.transcript = transcript
    job.language = (language or "es").lower()

    # summaries: dict {"es": "...", "pt": "..."}
    summaries_dict = {}
    if isinstance(job.summaries, dict):
        summaries_dict = dict(job.summaries)
    elif isinstance(job.summaries, str) and job.summaries.strip():
        try:
            summaries_dict = json.loads(job.summaries)
        except Exception:
            summaries_dict = {}

    if summary_text:
        summaries_dict[job.language] = summary_text

    job.summaries = summaries_dict
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)


# -----------------------------------------------------------------------------
# S3 helpers
# -----------------------------------------------------------------------------
def _s3_client():
    return boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

def _s3_read_all(bucket: str, key: str, max_retries: int = 3) -> bytes:
    """
    Descarga el objeto S3 completo a memoria con reintentos por si hay
    errores de streaming (ResponseStreamingError / IncompleteRead).
    """
    client = _s3_client()
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
            # Nota: Body es botocore.response.StreamingBody
            data = obj["Body"].read()
            if not data or len(data) < 16:
                raise IOError("Archivo vacío o dañado (bytes insuficientes).")
            return data
        except Exception as e:
            last_exc = e
            logger.warning("S3 read failed (attempt %d/%d): %s", attempt, max_retries, e)
            time.sleep(0.6 * attempt)
    raise last_exc or RuntimeError("Fallo desconocido leyendo S3")


# -----------------------------------------------------------------------------
# Idiomas soportados (para prompts y normalización)
# -----------------------------------------------------------------------------
LANG_NAME = {
    "es": "español",
    "en": "inglés",
    "pt": "portugués",
    "fr": "francés",
    "it": "italiano",
    "de": "alemán",
    "ca": "catalán",
    "gl": "gallego",
    "eu": "euskera",
    "nl": "neerlandés",
    "sv": "sueco",
    "no": "noruego",
    "da": "danés",
    "fi": "finés",
    "ru": "ruso",
    "pl": "polaco",
    "uk": "ucraniano",
    "tr": "turco",
    "ar": "árabe",
    "he": "hebreo",
    "fa": "persa",
    "hi": "hindi",
    "bn": "bengalí",
    "ta": "tamil",
    "te": "telugu",
    "zh": "chino",
    "ja": "japonés",
    "ko": "coreano",
    "ro": "rumano",
    "cs": "checo",
    "el": "griego",
    "hu": "húngaro",
    "vi": "vietnamita",
    "id": "indonesio",
    "ms": "malayo",
    # agrega más si necesitas
}

def _normalize_lang(lang: str | None) -> str:
    if not lang:
        return "es"
    l = lang.strip().lower()
    # Permite 'zh-cn', 'pt-br', etc. -> 'zh', 'pt'
    if "-" in l:
        l = l.split("-", 1)[0]
    return l if l in LANG_NAME else "es"


# -----------------------------------------------------------------------------
# Detección de idioma (con OpenAI, salida ISO-639-1)
# -----------------------------------------------------------------------------
def _detect_language_with_openai(text: str) -> str:
    """
    Devuelve un código ISO-639-1 en minúsculas. Si falla, 'es'.
    """
    try:
        client = _get_openai()
        # Modelo ligero y barato
        model = os.getenv("SUMMARY_MODEL", "gpt-4o-mini")
        prompt = (
            "Detecta el idioma del siguiente texto. "
            "Responde únicamente con el código ISO-639-1 (2 letras), en minúsculas. "
            "Si dudas entre varios, elige el más probable. Texto:\n\n" + text[:4000]
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un detector de idioma. Respondes solo el código ISO-639-1."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=4,
        )
        code = (resp.choices[0].message.content or "").strip().lower()
        if len(code) >= 2:
            code = code[:2]
        return _normalize_lang(code)
    except Exception as e:
        logger.warning("Fallo detectando idioma con OpenAI: %s", e)
        return "es"


# -----------------------------------------------------------------------------
# Resumen en el mismo idioma que la transcripción
# -----------------------------------------------------------------------------
def _summarize_in_language(transcript: str, lang_code: str) -> str:
    """
    Crea un resumen breve (5-8 líneas) en el idioma indicado por lang_code.
    """
    try:
        client = _get_openai()
        model = os.getenv("SUMMARY_MODEL", "gpt-4o-mini")
        idioma_nombre = LANG_NAME.get(lang_code, "español")
        system = (
            f"Eres un asistente que resume textos en {idioma_nombre}. "
            f"Debes mantener el idioma {idioma_nombre} siempre."
        )
        user = (
            f"Resume claramente el siguiente texto en {idioma_nombre}. "
            f"Extensión objetivo: 5–8 líneas.\n\n{transcript}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("Fallo creando resumen: %s", e)
        return ""


# -----------------------------------------------------------------------------
# Estimar duración (segundos) para ledger
# -----------------------------------------------------------------------------
def _estimate_seconds_from_transcript(transcript: str) -> int:
    """
    Aproximación sin dependencias: ~2.5 palabras por segundo (~150 WPM).
    """
    words = 0
    try:
        words = len(transcript.split())
    except Exception:
        words = max(1, len(transcript) // 5)
    secs = int(round(words / 2.5))
    return max(secs, 1)


def _add_usage_seconds(db, user_id: int, seconds: int):
    """
    Suma 'seconds' al ledger del mes actual para 'user_id'.
    """
    from sqlalchemy import select
    month_key = datetime.utcnow().strftime("%Y-%m")
    row = db.execute(
        select(UsageLedger).where(
            UsageLedger.user_id == user_id,
            UsageLedger.month_key == month_key,
        )
    ).scalar_one_or_none()

    if row is None:
        row = UsageLedger(user_id=user_id, month_key=month_key, seconds=0)

    row.seconds = int(row.seconds or 0) + int(seconds)
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()


# -----------------------------------------------------------------------------
# Tarea principal
# -----------------------------------------------------------------------------
@celery_app.task(name="transcribe_and_summarize", bind=True, max_retries=0)
def transcribe_and_summarize(self, job_id: int):
    """
    1) Leer job de DB.
    2) Descargar audio de S3.
    3) Transcribir (OpenAI whisper-1).
    4) Determinar idioma (si usuario eligió auto).
    5) Resumir en ese mismo idioma.
    6) Guardar transcript + summary + language + status=done.
    7) Registrar consumo estimado.
    """
    db = SessionLocal()
    try:
        job = _db_get_job(db, job_id)
        if not job:
            logger.error("Job %s no existe", job_id)
            return

        _job_set_status(db, job, "processing")

        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise RuntimeError("S3_BUCKET no está configurado.")

        # 1) Descargar bytes del audio
        data = _s3_read_all(bucket, job.audio_s3_key)

        # 2) Transcribir (OpenAI)
        client = _get_openai()
        model_asr = os.getenv("TRANSCRIBE_MODEL", "whisper-1")
        lang_hint = job.language if (job.language and job.language != "auto") else None

        # openai>=1.0 — archivo como file-like con nombre
        memfile = io.BytesIO(data)
        # Añadimos nombre para que la lib detecte el tipo (no es obligatorio pero ayuda)
        filename = job.filename or "audio.webm"
        # openai python SDK espera 'file' tipo archivo
        memfile.name = filename

        asr = client.audio.transcriptions.create(
            model=model_asr,
            file=memfile,
            language=lang_hint  # si el usuario eligió un idioma específico
        )
        transcript = (asr.text or "").strip()
        if not transcript:
            raise RuntimeError("Transcripción vacía.")

        # 3) Determinar idioma final
        if job.language and job.language != "auto":
            final_lang = _normalize_lang(job.language)
        else:
            final_lang = _detect_language_with_openai(transcript)

        # 4) Resumen en el mismo idioma
        summary = _summarize_in_language(transcript, final_lang)

        # 5) Guardar en DB
        _save_transcript_and_summary(db, job, transcript, final_lang, summary)
        _job_set_status(db, job, "done")

        # 6) Registrar consumo estimado
        seconds = _estimate_seconds_from_transcript(transcript)
        try:
            _add_usage_seconds(db, job.user_id or 1, seconds)
        except Exception as e:
            logger.warning("No se pudo actualizar usage ledger: %s", e)

    except Exception as e:
        logger.exception("Error en transcribe_and_summarize: %s", e)
        try:
            job = _db_get_job(db, job_id)
            if job:
                _job_set_status(db, job, "error", error=str(e))
        except Exception as e2:
            logger.error("No se pudo marcar error en DB: %s", e2)
    finally:
        db.close()
