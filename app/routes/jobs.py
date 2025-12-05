# app/routes/jobs.py
from __future__ import annotations

import os
import re
import math
import uuid
import tempfile
import datetime as dt
import subprocess
from typing import Optional, Dict, Any, List

from flask import Blueprint, request, jsonify, current_app, session
from app import db

# Modelos (tolerantes)
try:
    from app.models import AudioJob
except Exception:
    AudioJob = None  # type: ignore

try:
    from app.models_payment import Payment
except Exception:
    Payment = None  # type: ignore

# OpenAI
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

from sqlalchemy import inspect

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "")) if OpenAI else None
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
ASR_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")

MB = 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)
OPENAI_FILE_HARD_LIMIT_MB = int(os.getenv("OPENAI_FILE_LIMIT_MB", "25"))
MAX_CHUNK_SECONDS = int(os.getenv("MAX_CHUNK_SECONDS", "600"))

# =================================================================
# Utilidades de idioma / usuario / texto (las mismas que ya tenías)
# =================================================================
# ... (TODO lo que ya pegaste: _LANG_ALIASES, _normalize_lang, etc.)
# Para ahorrar espacio visual, asumo que copias el mismo bloque
# que tú ya tienes y que funciona correctamente.
# =================================================================

# (Aquí van _LANG_ALIASES, _normalize_lang, _lang_human, _get_user_id,
#  _dedupe_lines, _too_similar, _fallback_extractive_summary,
#  _summarize_llm, _summarize_robust, y toda la parte de ffmpeg)

# =================================================================
# Rutas
# =================================================================

bp = Blueprint("jobs", __name__)


@bp.route("/jobs", methods=["POST"])
def create_job():
    uid = _get_user_id() or "guest"

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Falta archivo"}), 400

    # Límite de subida
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if MAX_UPLOAD_MB > 0 and size > MAX_UPLOAD_MB * MB:
        return jsonify({"error": f"El archivo supera {MAX_UPLOAD_MB} MB."}), 400

    language_raw = (request.form.get("language") or "auto").strip().lower()
    language_forced = False
    if language_raw and language_raw != "auto":
        language = _normalize_lang(language_raw, "en")
        language_forced = True
    else:
        language = "auto"

    tmpdir = tempfile.mkdtemp(prefix="polyscribe_")
    tmp_path = os.path.join(tmpdir, file.filename)
    file.save(tmp_path)

    orig_duration = _duration_seconds(tmp_path)

    parts = _prepare_for_openai(tmp_path, OPENAI_FILE_HARD_LIMIT_MB)
    if not parts:
        msg = (
            "No se pudo preparar el audio. Si el archivo supera "
            f"{OPENAI_FILE_HARD_LIMIT_MB} MB por petición y no hay ffmpeg, no es posible procesarlo."
        )
        return jsonify({"error": msg}), 400

    transcripts: List[str] = []
    detected_first: str = ""
    for idx, part in enumerate(parts, 1):
        asr = _transcribe_audio(part, None if language == "auto" else language)
        if idx == 1:
            detected_first = _normalize_lang(asr.get("language_detected") or language or "es", "es")
        transcripts.append(asr.get("transcript", "") or "")

    transcript = "\n".join(t for t in transcripts if t).strip()
    detected_lang = detected_first if language == "auto" else _normalize_lang(language, "en")

    summary = _summarize_robust(transcript, language_code=detected_lang)

    job_id: Optional[str] = None
    if AudioJob is not None:
        try:
            now = dt.datetime.utcnow()
            job = AudioJob(
                id=str(uuid.uuid4()),
                user_id=uid,
                filename=file.filename,
                original_filename=getattr(file, "filename", None) or file.filename,
                audio_s3_key="",
                local_path=None,
                mime_type=None,
                size_bytes=size,
                language=(language if language != "auto" else "auto"),
                language_forced=1 if language_forced else 0,
                language_detected=detected_lang or "",
                status="done",
                error=0,
                error_message=None,
                transcript=transcript,
                summary=summary,
                duration_seconds=orig_duration if orig_duration > 0 else None,
                model_used=None,
                cost_cents=None,
                created_at=now,
                updated_at=now,
            )
            db.session.add(job)
            db.session.commit()
            job_id = getattr(job, "id", None)
        except Exception as e:
            current_app.logger.error("DB save failed: %s", e)
            db.session.rollback()

    return jsonify(
        {
            "id": job_id,
            "job_id": job_id,
            "status": "done" if transcript else "error",
            "filename": file.filename,
            "language": (language if language != "auto" else "auto"),
            "language_detected": detected_lang,
            "transcript": transcript,
            "summary": summary,
        }
    ), 200


@bp.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    if AudioJob is None:
        return jsonify({"id": job_id, "status": "done"}), 200

    job = db.session.get(AudioJob, job_id)
    if not job:
        try:
            job = db.session.get(AudioJob, int(job_id))
        except Exception:
            job = None

    if not job:
        return jsonify({"error": "No existe"}), 404

    out = {
        "id": getattr(job, "id", job_id),
        "job_id": getattr(job, "id", job_id),
        "filename": getattr(job, "filename", ""),
        "language": getattr(job, "language", ""),
        "language_detected": getattr(job, "language_detected", ""),
        "transcript": getattr(job, "transcript", ""),
        "summary": getattr(job, "summary", ""),
        "status": getattr(job, "status", "done"),
        "created_at": str(getattr(job, "created_at", "")),
        "updated_at": str(getattr(job, "updated_at", "")),
    }
    return jsonify(out), 200


@bp.route("/api/history", methods=["GET"])
def history_api():
    limit = max(1, min(200, int(request.args.get("limit", "100"))))
    uid = _get_user_id() or "guest"

    items: List[Dict[str, Any]] = []

    if AudioJob is not None:
        q = db.session.query(AudioJob).filter(getattr(AudioJob, "user_id") == uid)
        try:
            rows = (
                q.order_by(getattr(AudioJob, "created_at").desc())
                .limit(limit)
                .all()
            )
            for r in rows:
                items.append(
                    {
                        "id": getattr(r, "id", None),
                        "job_id": getattr(r, "id", None),
                        "filename": getattr(r, "filename", ""),
                        "language": getattr(r, "language", ""),
                        "language_detected": getattr(r, "language_detected", ""),
                        "status": getattr(r, "status", "done"),
                        "created_at": str(getattr(r, "created_at", "")),
                        "updated_at": str(getattr(r, "updated_at", "")),
                    }
                )
        except Exception as e:
            current_app.logger.exception("history query failed: %s", e)

    return jsonify({"items": items}), 200

# =================================================================
#                     Balance por pagos (robusto)
# =================================================================


def _minutes_from_payments(uid: Optional[str]) -> int:
    """
    Suma los minutos comprados de la tabla payments.

    Solo usa columnas que existen en app.models_payment.Payment:
      - user_id
      - minutes
    """
    if Payment is None:
        return 0

    try:
        cols = {c["name"] for c in inspect(db.engine).get_columns("payments")}
        if "minutes" not in cols:
            return 0

        q = db.session.query(Payment)
        if "user_id" in cols and uid and uid != "guest":
            q = q.filter(getattr(Payment, "user_id") == uid)

        total = 0
        for p in q.all():
            total += int(getattr(p, "minutes", 0) or 0)

        return total
    except Exception as e:
        current_app.logger.error("minutes_from_payments failed: %s", e)
        return 0


@bp.route("/api/usage/balance", methods=["GET"])
def usage_balance():
    uid = _get_user_id() or "guest"

    free_min = int(os.getenv("FREE_TIER_MINUTES", "10") or 10)
    paid_min = _minutes_from_payments(uid)
    allowance_min = free_min + paid_min

    used_seconds = 0
    if AudioJob is not None and hasattr(AudioJob, "duration_seconds"):
        try:
            q = db.session.query(AudioJob).filter(getattr(AudioJob, "user_id") == uid)
            used_seconds = sum(int(getattr(r, "duration_seconds", 0) or 0) for r in q.all())
        except Exception:
            used_seconds = 0

    return jsonify(
        {
            "ok": True,
            "used_seconds": int(used_seconds),
            "allowance_seconds": int(allowance_min * 60),
            "file_limit_bytes": int(MAX_UPLOAD_MB * MB),
        }
    ), 200
