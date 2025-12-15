# app/routes/jobs.py
from __future__ import annotations

import os
import tempfile
import subprocess
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request, session

from app import db
from app.models import AudioJob
from app.models_payment import Payment

bp = Blueprint("jobs", __name__)  # POST /jobs, GET /jobs/<id>


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


def _ffprobe_duration_seconds(path: str) -> int:
    """
    Retorna duración en segundos usando ffprobe (si está disponible).
    Si no puede, retorna 0.
    """
    try:
        # ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 file
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
        if not out:
            return 0
        sec = float(out)
        return int(round(sec))
    except Exception:
        return 0


def _minutes_allowance_and_used(user_id: str) -> Dict[str, int]:
    free_min = int(current_app.config.get("FREE_TIER_MINUTES", 10))

    paid_min = 0
    try:
        q = db.session.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.status == "captured",
        )
        paid_min = sum(int(p.minutes or 0) for p in q.all())
    except Exception as e:
        current_app.logger.error("allowance: error pagos: %s", e)

    used_sec = 0
    try:
        qj = db.session.query(AudioJob).filter(
            AudioJob.user_id == user_id,
            AudioJob.status == "done",
        )
        used_sec = sum(int(j.duration_seconds or 0) for j in qj.all())
    except Exception as e:
        current_app.logger.error("allowance: error jobs: %s", e)

    allowance_sec = int((free_min + paid_min) * 60)
    return {"allowance_sec": allowance_sec, "used_sec": int(used_sec)}


def _openai_client():
    """
    OpenAI (openai==1.x) usando OPENAI_API_KEY.
    """
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise RuntimeError(f"OpenAI SDK no disponible: {e}")

    key = os.getenv("OPENAI_API_KEY") or current_app.config.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Falta OPENAI_API_KEY")
    return OpenAI(api_key=key)


def _transcribe_and_summarize(file_path: str, language: str) -> Dict[str, Any]:
    """
    Transcribe con Whisper y resume con GPT.
    - language: "auto" o "es"/"en"/...
    """
    client = _openai_client()

    whisper_model = os.getenv("PS_TRANSCRIBE_MODEL", "whisper-1")
    llm_model = os.getenv("PS_SUMMARY_MODEL", "gpt-4o-mini")

    # 1) Transcripción
    with open(file_path, "rb") as f:
        kwargs = {"model": whisper_model, "file": f}
        # Si no es auto, mandamos language (whisper-1 lo soporta)
        if language and language != "auto":
            kwargs["language"] = language

        tr = client.audio.transcriptions.create(**kwargs)  # type: ignore

    # openai sdk devuelve objeto con .text normalmente
    transcript = getattr(tr, "text", None) or (tr.get("text") if isinstance(tr, dict) else "") or ""
    detected = getattr(tr, "language", None) or (tr.get("language") if isinstance(tr, dict) else None)

    # 2) Resumen
    # Resumen en el idioma detectado si existe; si no, en el seleccionado; si no, español.
    target_lang = detected or (language if language != "auto" else "es")

    prompt = (
        "You are PolyScribe. Summarize the transcript for a busy professional.\n"
        "Return:\n"
        "1) 6-10 bullet points\n"
        "2) Key decisions (if any)\n"
        "3) Action items (if any)\n"
        "Write in this language: " + str(target_lang) + "\n\n"
        "Transcript:\n" + transcript
    )

    resp = client.responses.create(  # type: ignore
        model=llm_model,
        input=prompt,
    )

    # Extraer texto del response (SDK 1.x)
    summary = ""
    try:
        summary = resp.output_text  # type: ignore
    except Exception:
        summary = str(resp)

    return {
        "transcript": transcript,
        "summary": summary,
        "language_detected": detected or "",
    }


@bp.post("/jobs")
def create_job():
    user_id = _get_user_id()

    up = request.files.get("file")
    if not up:
        return jsonify({"ok": False, "error": "NO_FILE"}), 400

    language = (request.form.get("language") or "auto").strip().lower()
    filename = (up.filename or "").strip() or "audio"

    # Guardar temporal
    suffix = os.path.splitext(filename)[1] or ".bin"
    tmp_path = None

    try:
        fd, tmp_path = tempfile.mkstemp(prefix="ps_", suffix=suffix)
        os.close(fd)
        up.save(tmp_path)

        # Duración estimada ANTES (para validar créditos)
        dur_sec = _ffprobe_duration_seconds(tmp_path)

        # Validación de créditos (si se pudo medir duración)
        info = _minutes_allowance_and_used(user_id)
        remain_sec = max(0, info["allowance_sec"] - info["used_sec"])

        if dur_sec > 0 and remain_sec < dur_sec:
            return jsonify({"ok": False, "error": "NO_CREDITS"}), 402

        # Crear registro (para que el historial exista SIEMPRE)
        job = AudioJob(
            user_id=user_id,
            filename=filename,
            language=language,
            status="processing",
            duration_seconds=dur_sec if dur_sec > 0 else None,
        )
        db.session.add(job)
        db.session.commit()

        # Procesar
        result = _transcribe_and_summarize(tmp_path, language)

        job.transcript = result.get("transcript") or ""
        job.summary = result.get("summary") or ""
        job.language_detected = (result.get("language_detected") or "")[:16]
        job.status = "done"

        # Si ffprobe no dio duración, al menos marca 0 (para no romper el uso)
        if job.duration_seconds is None:
            job.duration_seconds = 0

        db.session.commit()

        return jsonify(
            {
                "ok": True,
                "id": job.id,
                "job_id": job.id,
                "filename": job.filename,
                "language": job.language,
                "language_detected": job.language_detected,
                "status": job.status,
                "duration_seconds": int(job.duration_seconds or 0),
                "transcript": job.transcript or "",
                "summary": job.summary or "",
            }
        )

    except Exception as e:
        current_app.logger.exception("create_job error: %s", e)
        # Intentar dejar job en error si se alcanzó a crear
        try:
            if "job" in locals() and job and job.id:
                job.status = "error"
                job.error = str(e)
                db.session.commit()
        except Exception:
            pass

        return jsonify({"ok": False, "error": "SERVER_ERROR", "details": str(e)}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    user_id = _get_user_id()

    job = (
        db.session.query(AudioJob)
        .filter(AudioJob.id == job_id, AudioJob.user_id == user_id)
        .first()
    )
    if not job:
        return jsonify({"ok": False, "error": "NOT_FOUND"}), 404

    return jsonify(
        {
            "ok": True,
            "id": job.id,
            "job_id": job.id,
            "filename": job.filename,
            "language": job.language,
            "language_detected": job.language_detected,
            "status": job.status,
            "duration_seconds": int(job.duration_seconds or 0),
            "transcript": job.transcript or "",
            "summary": job.summary or "",
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
    )
