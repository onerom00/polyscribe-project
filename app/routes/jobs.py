# app/routes/jobs.py
from __future__ import annotations

import os
import uuid
import tempfile
import subprocess
from typing import Optional

from flask import Blueprint, current_app, jsonify, request, session

from app import db
from app.models import AudioJob

bp = Blueprint("jobs", __name__)

MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)


def _get_user_id() -> str:
    raw = (
        session.get("user_id")
        or session.get("uid")
        or request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or os.getenv("DEV_USER_ID", "")
    )
    s = str(raw).strip() if raw else ""
    return s or "guest"


def _probe_duration_seconds(path: str) -> int:
    """
    Usa ffprobe para calcular duración real del audio/video.
    Si falla, devuelve 0 (pero no rompe el flujo).
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
        sec = float(out)
        return max(0, int(round(sec)))
    except Exception as e:
        current_app.logger.warning("ffprobe duration failed: %s", e)
        return 0


@bp.post("/jobs")
def create_job():
    user_id = _get_user_id()

    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "Selecciona un archivo."}), 400

    # tamaño (si el cliente manda content-length, esto es extra seguro)
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > MAX_MB * 1024 * 1024:
        return jsonify({"ok": False, "error": f"El archivo supera el límite de {MAX_MB} MB."}), 400

    lang = (request.form.get("language") or "auto").strip().lower()
    filename = (f.filename or "").strip() or "audio"

    job_id = str(uuid.uuid4())

    # Guardar temporalmente para calcular duración y para enviar a tu motor de transcripción
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[-1] or ".bin") as tmp:
        tmp_path = tmp.name
        f.save(tmp_path)

    duration_seconds = _probe_duration_seconds(tmp_path)

    # ✅ CREAR REGISTRO EN DB (desde el principio)
    job = AudioJob(
        id=job_id,
        user_id=user_id,
        filename=filename,
        language=lang,
        status="processing",
        duration_seconds=duration_seconds,
    )
    db.session.add(job)
    db.session.commit()

    try:
        # ==========================================================
        # AQUÍ llama a TU lógica real de transcripción + resumen.
        # Sustituye estas dos líneas por tu integración actual.
        # ==========================================================
        transcript_text = current_app.config.get("DEMO_TRANSCRIPT", "")  # placeholder
        summary_text = current_app.config.get("DEMO_SUMMARY", "")        # placeholder

        # Si tú ya tienes funciones internas tipo transcribe(tmp_path, lang)
        # entonces úsala aquí y setea transcript_text/summary_text.

        job.status = "done"
        job.transcript = transcript_text or ""
        job.summary = summary_text or ""
        job.language_detected = job.language_detected or (lang if lang != "auto" else None)

        db.session.commit()

        # ✅ RESPUESTA para tu front
        return jsonify(job.to_dict())

    except Exception as e:
        current_app.logger.exception("jobs: error procesando: %s", e)
        job.status = "error"
        job.error = str(e)
        db.session.commit()
        return jsonify({"ok": False, "error": "No se pudo procesar el archivo."}), 500

    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    user_id = _get_user_id()
    job = db.session.query(AudioJob).filter(AudioJob.id == job_id, AudioJob.user_id == user_id).first()
    if not job:
        return jsonify({"ok": False, "error": "Job no encontrado."}), 404
    return jsonify(job.to_dict())
