# app/routes/leads.py
from __future__ import annotations

import os
import re
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from flask import Blueprint, request, jsonify, current_app
from app import db

from app.models.lead import Lead

bp = Blueprint("leads", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _get_user_id() -> Optional[str]:
    # Respeta tu esquema actual: header X-User-Id o query ?user_id=
    uid = (request.headers.get("X-User-Id") or "").strip()
    if not uid:
        uid = (request.args.get("user_id") or "").strip()
    return uid or None

def _send_email(subject: str, body: str) -> None:
    """
    Enviar notificación por SMTP (Gmail App Password recomendado).
    Variables de entorno esperadas:
      SMTP_HOST (default: smtp.gmail.com)
      SMTP_PORT (default: 587)
      SMTP_USER
      SMTP_PASS
      LEADS_NOTIFY_TO (default: SMTP_USER)
    """
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    if not smtp_user or not smtp_pass:
        # Si no hay credenciales, no fallamos el lead. Solo log.
        current_app.logger.warning("SMTP not configured (SMTP_USER/SMTP_PASS missing). Lead saved without email.")
        return

    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    to_addr = os.getenv("LEADS_NOTIFY_TO", smtp_user).strip()

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, [to_addr], msg.as_string())

@bp.route("/api/leads", methods=["POST"])
def create_lead():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    note = (data.get("note") or "").strip()
    source = (data.get("source") or "").strip() or "unknown"
    user_id = data.get("user_id") or _get_user_id()

    if not email or not EMAIL_RE.match(email):
        return jsonify({"ok": False, "error": "EMAIL_INVALID"}), 400

    # Evitar duplicados “demasiado” (mismo email en últimas X entradas no es crítico,
    # pero mantenemos simple: permitimos repetidos si cambian campos).
    lead = Lead(email=email, name=name or None, note=note or None, user_id=user_id, source=source)
    db.session.add(lead)
    db.session.commit()

    # Notificación por email (opcional)
    try:
        subj = f"Nuevo lead en PolyScribe ({source})"
        body = (
            "Nuevo lead capturado:\n\n"
            f"Email: {email}\n"
            f"Nombre: {name or '-'}\n"
            f"Nota: {note or '-'}\n"
            f"User ID: {user_id or '-'}\n"
            f"Source: {source}\n"
            f"Lead ID: {lead.id}\n"
        )
        _send_email(subj, body)
    except Exception as e:
        current_app.logger.exception("Failed sending lead email: %s", e)

    return jsonify({"ok": True, "lead": lead.as_dict()}), 201
