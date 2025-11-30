# app/routes/history.py
from __future__ import annotations
from flask import Blueprint, render_template, url_for, request
from app import db

try:
    from app.models import AudioJob
except Exception:
    AudioJob = None  # type: ignore

history_bp = Blueprint("history", __name__)

@history_bp.route("/history", methods=["GET"])
def history_page():
    """
    Lista simple de los últimos 200 trabajos, sin filtrar por usuario.
    (Así siempre ves lo que se guardó, tengas o no sesión/config de DEV_USER_ID).
    """
    items = []
    if AudioJob is not None:
        try:
            rows = (
                db.session.query(AudioJob)
                .order_by(getattr(AudioJob, "id").desc())
                .limit(200)
                .all()
            )
            for r in rows:
                items.append({
                    "id": getattr(r, "id", None),
                    "filename": getattr(r, "filename", "") or f"job {getattr(r, 'id', '')}",
                    "language": getattr(r, "language", "") or "auto",
                    "language_detected": getattr(r, "language_detected", "") or "",
                    "status": getattr(r, "status", "done"),
                    "created_at": getattr(r, "created_at", None),
                })
        except Exception:
            items = []

    # Sin necesidad de user_id; el botón Ver va directo con ?job_id=...
    base_query = {}
    return render_template("history.html", items=items, base_query=base_query)

@history_bp.route("/api/jobs/<int:job_id>.json", methods=["GET"])
def history_job_json(job_id: int):
    """
    Exporta el job como JSON para el botón "JSON" del historial.
    """
    from flask import jsonify

    if AudioJob is None:
        return jsonify({"error": "No model"}), 404

    r = db.session.get(AudioJob, job_id)
    if not r:
        return jsonify({"error": "No existe"}), 404

    return jsonify({
        "id": getattr(r, "id", None),
        "filename": getattr(r, "filename", ""),
        "language": getattr(r, "language", ""),
        "language_detected": getattr(r, "language_detected", ""),
        "status": getattr(r, "status", "done"),
        "transcript": getattr(r, "transcript", ""),
        "summary": getattr(r, "summary", ""),
        "created_at": str(getattr(r, "created_at", "")),
        "updated_at": str(getattr(r, "updated_at", "")),
    }), 200
