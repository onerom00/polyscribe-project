# app/routes_summarize.py
import os
from flask import Blueprint, jsonify, request, session, current_app
from app import db
from app.models_job import AudioJob

bp = Blueprint("summarize", __name__, url_prefix="/api")

try:
    from app.utils_auth import get_request_user_id
except Exception:
    def get_request_user_id():
        uid = session.get("user_id") or session.get("uid") or request.headers.get("X-User-Id")
        try:
            return int(uid) if uid is not None else None
        except Exception:
            return None

# OpenAI client (opcional; si no está, devolvemos error amigable)
try:
    from openai import OpenAI
    _client = OpenAI()
except Exception:
    _client = None

@bp.post("/summarize")
def summarize_api():
    """
    Body JSON:
      { "job_id": "<uuid>", "lang": "es|en|..." }
    """
    uid = get_request_user_id()
    if not uid:
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    data = request.get_json(silent=True) or {}
    job_id = (data.get("job_id") or "").strip()
    lang = (data.get("lang") or "es").strip().lower()

    if not job_id:
        return jsonify({"ok": False, "error": "job_id_missing"}), 400

    job = db.session.get(AudioJob, job_id)
    if not job or job.user_id != uid:
        return jsonify({"ok": False, "error": "job_not_found"}), 404

    if not (job.transcript and job.transcript.strip()):
        return jsonify({"ok": False, "error": "no_transcript"}), 400

    if not _client:
        return jsonify({"ok": False, "error": "openai_not_available"}), 503

    # Modelo ligero para resumen
    model = os.getenv("SUMMARIZER_MODEL", "gpt-4o-mini")

    prompt = (
        f"Resumen conciso en {lang} del siguiente texto. "
        "Devuelve 5–8 viñetas con lo esencial y, si procede, acciones clave.\n\n"
        f"Texto:\n{job.transcript.strip()}\n"
    )

    try:
        # puedes usar responses.create si prefieres
        chat = _client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un asistente que resume transcripciones con claridad."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        summary = (chat.choices[0].message.content or "").strip()

        job.summary = summary
        db.session.commit()

        return jsonify({"ok": True, "job_id": job.id, "summary": summary}), 200

    except Exception as e:
        current_app.logger.exception("summarize failed: %s", e)
        return jsonify({"ok": False, "error": "summarize_failed", "detail": str(e)}), 500
