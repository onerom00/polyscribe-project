# app/services/mailer.py
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Optional

from flask import current_app


def send_email(to_email: str, subject: str, html: str, text: Optional[str] = None) -> None:
    """
    Env vars esperadas (Render):
      SMTP_HOST=smtp.gmail.com
      SMTP_PORT=587
      SMTP_USER=helppolyscribe@gmail.com
      SMTP_PASS=APP_PASSWORD_DE_GMAIL
      MAIL_FROM=helppolyscribe@gmail.com
      MAIL_FROM_NAME=PolyScribe
    """
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")

    mail_from = os.getenv("MAIL_FROM", user)
    from_name = os.getenv("MAIL_FROM_NAME", "PolyScribe")

    if not user or not password:
        current_app.logger.warning("SMTP not configured: missing SMTP_USER/SMTP_PASS")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{mail_from}>"
    msg["To"] = to_email

    if text:
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content("Tu cliente de correo no soporta HTML.")
        msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
