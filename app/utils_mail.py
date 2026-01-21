# app/utils_mail.py
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from flask import current_app


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    host = current_app.config.get("SMTP_HOST")
    port = int(current_app.config.get("SMTP_PORT", 587))
    user = current_app.config.get("SMTP_USER")
    password = current_app.config.get("SMTP_PASS")
    mail_from = current_app.config.get("MAIL_FROM") or user

    if not host or not port or not user or not password or not mail_from:
        raise RuntimeError("SMTP no configurado (SMTP_HOST/PORT/USER/PASS/MAIL_FROM)")

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)

    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(msg)
