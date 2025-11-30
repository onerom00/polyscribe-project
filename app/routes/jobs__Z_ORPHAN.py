# app/routes/jobs.py
from __future__ import annotations
import os, time, math, shutil, tempfile
from datetime import datetime
from typing import Optional, Tuple

import httpx
from flask import Blueprint, request, jsonify, current_app

from .. import db
from ..models import User, AudioJob, UsageLedger

bp = Blueprint("jobs", __name__, url_prefix="")  # sin prefijo, rutas como /jobs

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

# -------- Helpers de usuario --------
def _get_current_user() -> Optional[User]:
    raw = (
        request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or (current_app.config.get("DEV_USER_ID") and str(current_app.config.get("DEV_USER_ID")))
    )
    try:
        uid = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    if not uid:
        return None
    return db.session.get(User, uid)

def _require_user() -> Tuple[Optional[User], Optional[any]]:
    user = _get_current_user()
    if not user:
        return None, (jsonify({"error": "Usuario no encontrado"}), 401)
    if not user.is_active:
        return None, (jsonify({"error": "Usuario inactivo"}), 403)
    return user, None

# -------- OpenAI helpers --------
def _openai_headers() -> dict:
    key = os.getenv("OPENAI_API_KEY") or current_app.config.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY no configurada.")
    return {"Authorization": f"Bearer {key}"}

def transcribe_with_openai(local_path: str, language: str = "auto") -> dict:
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = _openai_headers()
    files = {"file": (os.path.basename(local_path), open(local_path, "rb"), "application/octet-stream")}
    data = {"model": OPENAI_TRANSCRIBE_MODEL, "temperature": "0", "response_format": "verbose_json"}
    if language and language != "auto":
        data["language"] = language
    with httpx.Client(timeout=120) as client:
        r = client.post(url, headers=headers, data=data, files=files)
        r.raise_for_status()
        return r.json()

def summarize_with_openai(transcript: str, out_lang_code: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {**_openai_headers(), "Content-Type": "application/json"}
    out_lang = "es" if not out_lang_code or out_lang_code == "auto" else out_lang_code
    system = ("Eres un asistente que genera resúmenes breves y claros. "
              "Devuelve 4–6 oraciones máximo, con viñetas si conviene. "
              "No inventes; usa solo la transcripción.")
    user_msg = f"Idioma de salida: {out_lang}\n\nTranscripción:\n{transcript.strip()}"
    payload = {"model": OPENAI_CHAT_MODEL, "temperature": 0.2,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user_msg}],
               "max_tokens": 400}
    with httpx.Client(timeout=120) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return (data["choices"][0]["message"]["content"] or "").strip()

# -------- Badge de uso --------
@bp.get("/api/usage/balance")
def usage_balance():
    user = _get_current_user()
    if not user:
        return jsonify({"used_seconds": 0, "allowance_seconds": 0, "plan_tier": "free"})
    used_min = int(user.minutes_used or 0)
    quota_min = int(user.minute_quota or 0)
    return jsonify({"used_seconds": used_min * 60, "allowance_seconds": quota_min * 60,
                    "plan_tier": user.plan_tier or "free"})

# -------- Jobs --------
@bp.post("/jobs")
def create_job():
    user, err = _require_user()
    if err:
        return err

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Falta archivo."}), 400

    # límite de tamaño
    file.stream.seek(0, os.SEEK_END); size = file.stream.tell(); file.stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        return jsonify({"error": "El archivo supera 25 MB."}), 400

    language = (request.form.get("language") or "auto").strip().lower()
    filename = file.filename or f"audio_{int(time.time())}.bin"

    tmpdir = tempfile.mkdtemp(prefix="polys-")
    local_path = os.path.join(tmpdir, filename)
    file.save(local_path)

    job = AudioJob(user_id=user.id, filename=filename, original_filename=filename,
                   language=language or "auto", status="queued", audio_s3_key="",
                   local_path=local_path, size_bytes=size, mime_type=None)
    db.session.add(job); db.session.commit()

    try:
        job.status = "processing"; db.session.commit()

        tr = transcribe_with_openai(local_path, language=language)
        transcript = (tr.get("text") or "").strip()
        detected = tr.get("language") or None
        duration = tr.get("duration")

        job.transcript = transcript
        if detected: job.language_detected = detected
        if duration:
            try: job.duration_seconds = int(duration)
            except Exception: pass

        summary = ""
        if transcript:
            summary = summarize_with_openai(transcript, out_lang_code=language)
        job.summary = summary

        job.status = "done"
        job.model_used = OPENAI_TRANSCRIBE_MODEL
        job.updated_at = datetime.utcnow()

        # consumo estimado
        used_minutes_add = 0
        if job.duration_seconds:
            used_minutes_add = math.ceil(job.duration_seconds / 60)
        elif transcript:
            words = len(transcript.split()); used_minutes_add = max(1, math.ceil(words / 160))

        if used_minutes_add:
            user.minutes_used = int(user.minutes_used or 0) + used_minutes_add
            db.session.add(UsageLedger(user_id=user.id, minutes_delta=used_minutes_add, reason="transcription"))

        db.session.commit()

    except httpx.HTTPStatusError as e:
        job.status = "error"; job.error_message = f"OpenAI HTTP error: {e.response.status_code} {e.response.text[:300]}"
        db.session.commit(); return jsonify({"error": "Fallo al contactar con OpenAI."}), 500
    except Exception as e:
        job.status = "error"; job.error_message = str(e)[:500]
        db.session.commit(); return jsonify({"error": "No se pudo iniciar el proceso."}), 500
    finally:
        try:
            if os.path.isdir(tmpdir): shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    return jsonify({"id": job.id, "job_id": job.id})

@bp.get("/jobs/<int:job_id>")
def get_job(job_id: int):
    user, err = _require_user()
    if err:
        return err
    job = db.session.get(AudioJob, job_id)
    if not job or job.user_id != user.id:
        return jsonify({"error": "Job no encontrado."}), 404
    return jsonify({
        "id": job.id, "filename": job.filename, "status": job.status,
        "error": job.error_message, "language": job.language_detected or job.language or "auto",
        "transcript": job.transcript or "", "summary": job.summary or "",
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    })
