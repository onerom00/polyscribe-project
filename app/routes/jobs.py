# app/routes/jobs.py
from __future__ import annotations

import os
import re
import json
import math
import tempfile
import datetime as dt
import subprocess
from typing import Optional, Dict, Any, List

from flask import Blueprint, request, jsonify, current_app, session

from app.extensions import db
from app.models import AudioJob
from app.models_user import User  # ÚNICA fuente de User


try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "")) if OpenAI else None
ASR_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

MB = 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)
OPENAI_FILE_HARD_LIMIT_MB = int(os.getenv("OPENAI_FILE_LIMIT_MB", "25"))
MAX_CHUNK_SECONDS = int(os.getenv("MAX_CHUNK_SECONDS", "600"))

bp = Blueprint("jobs", __name__)  # sin url_prefix: tus rutas ya están completas


_LANG_ALIASES: Dict[str, str] = {
    "es": "es", "spa": "es", "spanish": "es", "español": "es", "es-es": "es",
    "en": "en", "eng": "en", "english": "en", "en-us": "en", "en-gb": "en",
    "pt": "pt", "por": "pt", "portuguese": "pt", "português": "pt", "pt-br": "pt", "pt-pt": "pt",
    "fr": "fr", "fra": "fr", "fre": "fr", "french": "fr", "français": "fr",
    "it": "it", "ita": "it", "italian": "it", "italiano": "it",
    "de": "de", "deu": "de", "ger": "de", "german": "de", "deutsch": "de",
    "ca": "ca", "cat": "ca", "catalan": "ca", "català": "ca",
    "gl": "gl", "glg": "gl", "galician": "gl", "galego": "gl",
    "eu": "eu", "eus": "eu", "basque": "eu", "euskara": "eu",
    "nl": "nl", "nld": "nl", "dut": "nl", "dutch": "nl",
    "pl": "pl", "pol": "pl", "polish": "pl",
    "uk": "uk", "ukr": "uk", "ukrainian": "uk",
    "ru": "ru", "rus": "ru", "russian": "ru",
    "tr": "tr", "tur": "tr", "turkish": "tr",
    "cs": "cs", "ces": "cs", "cze": "cs", "czech": "cs",
    "sk": "sk", "slk": "sk", "slo": "sk", "slovak": "sk",
    "sl": "sl", "slv": "sl", "slovenian": "sl",
    "ro": "ro", "ron": "ro", "rum": "ro", "romanian": "ro",
    "hu": "hu", "hun": "hu", "hungarian": "hu",
    "bg": "bg", "bul": "bg", "bulgarian": "bg",
    "hr": "hr", "hrv": "hr", "croatian": "hr",
    "sr": "sr", "srp": "sr", "serbian": "sr",
    "sv": "sv", "swe": "sv", "swedish": "sv",
    "no": "no", "nor": "no", "norwegian": "no",
    "da": "da", "dan": "da", "danish": "da",
    "fi": "fi", "fin": "fi", "finnish": "fi",
    "et": "et", "est": "et", "estonian": "et",
    "lv": "lv", "lav": "lv", "latvian": "lv",
    "lt": "lt", "lit": "lt", "lithuanian": "lt",
    "el": "el", "ell": "el", "gre": "el", "greek": "el",
    "he": "he", "heb": "he", "hebrew": "he",
    "ar": "ar", "ara": "ar", "arabic": "ar",
    "fa": "fa", "fas": "fa", "per": "fa", "persian": "fa", "farsi": "fa",
    "ur": "ur", "urd": "ur", "urdu": "ur",
    "hi": "hi", "hin": "hi", "hindi": "hi",
    "bn": "bn", "ben": "bn", "bengali": "bn",
    "ta": "ta", "tam": "ta", "tamil": "ta",
    "te": "te", "tel": "te", "telugu": "te",
    "th": "th", "tha": "th", "thai": "th",
    "vi": "vi", "vie": "vi", "vietnamese": "vi",
    "id": "id", "ind": "id", "indonesian": "id",
    "ms": "ms", "msa": "ms", "may": "ms", "malay": "ms",
    "sw": "sw", "swa": "sw", "swahili": "sw",
    "zh": "zh", "zho": "zh", "chi": "zh", "chinese": "zh", "mandarin": "zh", "zh-cn": "zh",
    "ja": "ja", "jpn": "ja", "japanese": "ja",
    "ko": "ko", "kor": "ko", "korean": "ko",
}


def _normalize_lang(code_or_name: Optional[str], default: str = "es") -> str:
    """
    Normaliza códigos/nombres conocidos sin convertir automáticamente
    los idiomas desconocidos a español.
    """
    if not code_or_name:
        return default

    s = str(code_or_name).strip().lower().replace("_", "-")
    if not s:
        return default

    if s in _LANG_ALIASES:
        return _LANG_ALIASES[s]

    if "-" in s:
        primary = s.split("-", 1)[0]
        if primary in _LANG_ALIASES:
            return _LANG_ALIASES[primary]
        if re.fullmatch(r"[a-z]{2,3}", primary):
            return primary

    if re.fullmatch(r"[a-z]{2,3}", s):
        return s

    return default


def _require_auth_user_id() -> str | None:
    """
    Auth PROD: el user_id real viene de la sesión.
    Si AUTH_REQUIRE_VERIFIED_EMAIL=1, también exige is_verified=True.
    Devuelve string del id, por ejemplo "12", o None si no autorizado.
    """
    uid = session.get("user_id") or session.get("uid")
    if not uid:
        return None

    try:
        u = db.session.get(User, int(uid))
    except Exception:
        u = None

    if not u or not getattr(u, "is_active", True):
        return None

    must_verify = bool(current_app.config.get("AUTH_REQUIRE_VERIFIED_EMAIL", True))
    if must_verify and not getattr(u, "is_verified", False):
        return None

    return str(int(u.id))


def _get_free_tier_minutes() -> int:
    """
    Fuente robusta para el plan gratis:
    1) Variable de entorno FREE_TIER_MINUTES
    2) Config Flask FREE_TIER_MINUTES
    3) Default seguro: 5 minutos
    """
    raw = os.getenv("FREE_TIER_MINUTES", current_app.config.get("FREE_TIER_MINUTES", 5))
    try:
        return int(raw or 5)
    except Exception:
        return 5


def _send_email(to_email: str, subject: str, html_body: str) -> None:
    """
    Envío SMTP simple usando las variables ya configuradas en Render:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.utils import parseaddr

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    pw = os.getenv("SMTP_PASS", "")
    from_addr = os.getenv("SMTP_FROM", f"PolyScribe <{user}>")

    if not user or not pw:
        current_app.logger.warning(
            "SMTP not configured. Skipping email to=%s subject=%s",
            to_email,
            subject,
        )
        return

    envelope_from = parseaddr(from_addr)[1] or user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, pw)
        smtp.sendmail(envelope_from, [to_email], msg.as_string())


def _pricing_url() -> str:
    base = (current_app.config.get("APP_BASE_URL") or os.getenv("APP_BASE_URL") or "").strip()
    base = base.rstrip("/") or "https://www.getpolyscribe.com"
    return f"{base}/pricing"


def _send_usage_email_once(user_id: str, kind: str, remaining_seconds: int = 0) -> None:
    """
    Emails comerciales mínimos:
    - low_minutes: cuando queda 1 minuto o menos.
    - no_credits: cuando intenta procesar y no tiene minutos suficientes.

    Durante las pruebas comerciales, low_minutes puede enviarse más de una vez
    para confirmar que el disparador funciona correctamente.
    no_credits sí queda protegido por sesión para evitar repetición excesiva.
    """
    session_key = f"usage_email_sent_{kind}_{user_id}"

    # Permitimos repetir low_minutes durante pruebas.
    # Protegemos no_credits para evitar correos repetidos en la misma sesión.
    if kind != "low_minutes" and session.get(session_key):
        return

    try:
        user = db.session.get(User, int(user_id))
    except Exception:
        user = None

    email = (getattr(user, "email", "") or "").strip()
    if not email or "@" not in email:
        return

    pricing = _pricing_url()
    remaining_min = max(0, remaining_seconds) / 60

    if kind == "low_minutes":
        subject = "Tu saldo de minutos en PolyScribe está bajo"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;line-height:1.5;color:#111827">
          <h2 style="margin-bottom:12px">Tu saldo de minutos está bajo</h2>

          <p>Tu cuenta de PolyScribe está cerca de agotar los minutos disponibles.</p>

          <p>
            Saldo aproximado disponible:
            <strong>{remaining_min:.1f} min</strong>
          </p>

          <p>
            Puedes revisar los planes disponibles para seguir transcribiendo,
            resumiendo y exportando tus archivos sin interrupciones.
          </p>

          <p style="margin:22px 0">
            <a href="{pricing}" style="background:#0b62e0;color:#ffffff;padding:11px 16px;border-radius:8px;text-decoration:none;font-weight:800;display:inline-block">
              Ver planes
            </a>
          </p>

          <p style="color:#6b7280;font-size:12px">
            PolyScribe · Transcripción, resumen y exportación en minutos.
          </p>
        </div>
        """
    elif kind == "no_credits":
        subject = "Actualiza tu saldo de minutos en PolyScribe"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;line-height:1.5;color:#111827">
          <h2 style="margin-bottom:12px">Tu saldo de minutos necesita actualizarse</h2>

          <p>
            Intentaste procesar un archivo, pero tu cuenta no tiene minutos suficientes disponibles.
          </p>

          <p>
            Para seguir usando PolyScribe, puedes revisar los planes disponibles
            y añadir más minutos a tu cuenta.
          </p>

          <p style="margin:22px 0">
            <a href="{pricing}" style="background:#22c55e;color:#0b111d;padding:11px 16px;border-radius:8px;text-decoration:none;font-weight:900;display:inline-block">
              Ver planes
            </a>
          </p>

          <p style="color:#6b7280;font-size:12px">
            Tus transcripciones anteriores se conservan en tu historial.
          </p>
        </div>
        """
    else:
        return

    try:
        _send_email(email, subject, html)

        # Solo marcamos como enviado en sesión los emails distintos de low_minutes.
        # Así podemos probar low_minutes varias veces mientras ajustamos el embudo.
        if kind != "low_minutes":
            session[session_key] = True
            session.modified = True

        current_app.logger.info(
            "usage email sent kind=%s user_id=%s email=%s remaining_seconds=%s",
            kind,
            user_id,
            email,
            remaining_seconds,
        )
    except Exception as e:
        current_app.logger.error(
            "usage email failed kind=%s user_id=%s error=%s",
            kind,
            user_id,
            e,
        )


def _ffmpeg() -> str:
    return os.getenv("FFMPEG_BIN", "ffmpeg")


def _ffprobe() -> str:
    return os.getenv("FFPROBE_BIN", "ffprobe")


def _have_ffmpeg() -> bool:
    try:
        subprocess.run([_ffmpeg(), "-version"], capture_output=True, check=False)
        subprocess.run([_ffprobe(), "-version"], capture_output=True, check=False)
        return True
    except Exception:
        return False


def _file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / MB
    except Exception:
        return 0.0


def _duration_seconds(path: str) -> float:
    try:
        r = subprocess.run(
            [
                _ffprobe(),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                path,
            ],
            capture_output=True,
            check=False,
        )
        s = (r.stdout.decode(errors="ignore").strip() or "0")
        return float(s)
    except Exception:
        return 0.0


def _compress_to_opus(src: str, dst: str, bitrate: str = "64k") -> bool:
    try:
        cmd = [
            _ffmpeg(),
            "-y",
            "-i",
            src,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "libopus",
            "-b:a",
            bitrate,
            dst,
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        return os.path.exists(dst) and _file_size_mb(dst) > 0
    except Exception:
        return False


def _split_audio(src: str, out_dir: str, chunk_seconds: int) -> List[str]:
    dur = _duration_seconds(src)
    if dur <= 0:
        return [src]

    parts: List[str] = []
    start, idx = 0.0, 1

    while start < dur - 0.1:
        out = os.path.join(out_dir, f"part_{idx:03d}.ogg")
        cmd = [
            _ffmpeg(),
            "-y",
            "-ss",
            f"{start:.2f}",
            "-i",
            src,
            "-t",
            str(chunk_seconds),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "libopus",
            "-b:a",
            "64k",
            out,
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        if os.path.exists(out) and _file_size_mb(out) > 0:
            parts.append(out)
        idx += 1
        start += float(chunk_seconds)

    return parts or [src]


def _prepare_for_openai(path: str, hard_limit_mb: int) -> List[str]:
    if _file_size_mb(path) <= hard_limit_mb:
        return [path]

    if not _have_ffmpeg():
        return []

    tmpdir = tempfile.mkdtemp(prefix="prep_")
    compressed = os.path.join(tmpdir, "compressed.ogg")

    if not _compress_to_opus(path, compressed, bitrate="48k"):
        return []

    if _file_size_mb(compressed) <= hard_limit_mb:
        return [compressed]

    return _split_audio(compressed, tmpdir, MAX_CHUNK_SECONDS)


def _dedupe_lines(txt: str) -> str:
    lines = [l.strip() for l in (txt or "").splitlines() if l and l.strip()]
    seen, out = set(), []

    for l in lines:
        key = re.sub(r"\W+", " ", l.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(l)

    return "\n".join(out)


def _fallback_extractive_summary(text: str, max_sents: int = 5) -> str:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    if not sents:
        return ""

    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ']+", text or "")
    freq: Dict[str, int] = {}

    for w in words:
        wl = w.lower()
        if len(wl) <= 2:
            continue
        freq[wl] = freq.get(wl, 0) + 1

    def score(sent: str) -> float:
        tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ']+", sent.lower())
        if not tokens:
            return 0.0
        return sum(freq.get(t, 0) for t in tokens) / math.sqrt(len(tokens))

    ranked = sorted(((score(s), i, s) for i, s in enumerate(sents)), reverse=True)
    top = sorted(ranked[:max_sents], key=lambda t: t[1])

    return "\n".join("• " + s.strip() for _, _, s in top)


def _summarize_llm(clean_text: str, language_code: str = "es") -> str:
    """Resumen en un idioma seleccionado manualmente."""
    if not _client:
        return ""

    system = (
        f"You summarize in {language_code}. "
        "Return 3–6 bullet points. Be abstract. Do not copy phrases. "
        "Do not translate to another language."
    )
    user = f"Text:\n\n{clean_text}\n\nSummarize now."

    resp = _client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    out = (resp.choices[0].message.content or "").strip()
    if "•" not in out:
        lines = [l.strip("-• ").strip() for l in out.splitlines() if l.strip()]
        out = "\n".join("• " + l for l in lines)

    return out


def _summarize_robust(raw_text: str, language_code: str = "es") -> str:
    cleaned = _dedupe_lines(raw_text or "")
    if not cleaned:
        return ""

    try:
        out = _summarize_llm(cleaned, _normalize_lang(language_code, "es"))
        return out or _fallback_extractive_summary(cleaned, 5)
    except Exception as e:
        current_app.logger.warning("Summary failed: %s", e)
        return _fallback_extractive_summary(cleaned, 5)


def _summarize_auto_llm(clean_text: str, whisper_hint: str = "") -> tuple[str, str]:
    """
    En modo Auto, una sola llamada:
    1) confirma el idioma dominante a partir del texto,
    2) genera el resumen en ese mismo idioma,
    3) no traduce.
    """
    if not _client:
        return _normalize_lang(whisper_hint, "und"), ""

    hint = (whisper_hint or "").strip() or "unknown"

    system = (
        "You are a language detector and summarizer. "
        "Determine the dominant language from the transcription text itself. "
        "The ASR language hint is only a hint and may be wrong. "
        "Write the summary in exactly the same dominant language as the transcription; never translate it. "
        "Return ONLY valid JSON with this structure: "
        '{"language":"ISO-639-1 two-letter code when possible","summary":["point 1","point 2","point 3"]}. '
        "Return 3 to 6 concise, abstract summary points."
    )
    user = f"ASR language hint: {hint}\n\nTranscription:\n{clean_text}"

    resp = _client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    raw = (resp.choices[0].message.content or "").strip()
    match = re.search(r"\{.*\}", raw, flags=re.S)
    payload = json.loads(match.group(0) if match else raw)

    lang_raw = payload.get("language") or whisper_hint or "und"
    lang = _normalize_lang(lang_raw, _normalize_lang(whisper_hint, "und"))

    summary_value = payload.get("summary") or []
    if isinstance(summary_value, list):
        points = [str(x).strip() for x in summary_value if str(x).strip()]
    else:
        points = [l.strip("-• ").strip() for l in str(summary_value).splitlines() if l.strip()]

    summary = "\n".join("• " + p for p in points[:6])
    return lang, summary


def _summarize_auto_robust(raw_text: str, whisper_hint: str = "") -> tuple[str, str]:
    cleaned = _dedupe_lines(raw_text or "")
    if not cleaned:
        return _normalize_lang(whisper_hint, "und"), ""

    try:
        detected_lang, summary = _summarize_auto_llm(cleaned, whisper_hint)
        if summary:
            return detected_lang or _normalize_lang(whisper_hint, "und"), summary
    except Exception as e:
        current_app.logger.warning("Auto language/summary failed: %s", e)

    # El fallback extractivo conserva el idioma original porque no traduce.
    return _normalize_lang(whisper_hint, "und"), _fallback_extractive_summary(cleaned, 5)


def _transcribe_audio(path: str, language_code: Optional[str]) -> Dict[str, Any]:
    if not _client:
        return {
            "transcript": "",
            "language_detected": _normalize_lang(language_code, "und"),
        }

    model = ASR_MODEL or "whisper-1"
    lang = None if (not language_code or language_code == "auto") else _normalize_lang(language_code, "en")

    with open(path, "rb") as f:
        try:
            res = _client.audio.transcriptions.create(
                model=model,
                file=f,
                language=lang,
                response_format="verbose_json",
            )
            text = (res.text or "").strip()
            det_raw = getattr(res, "language", None) or lang or "und"
            det = _normalize_lang(det_raw, str(det_raw).strip().lower() or "und")
            return {"transcript": text, "language_detected": det}
        except Exception as e:
            current_app.logger.warning("ASR failed: %s", e)
            return {
                "transcript": "",
                "language_detected": _normalize_lang(lang, "und"),
            }


def _get_allowance_seconds(user_id: str) -> int:
    free_min = _get_free_tier_minutes()

    paid_min = 0
    try:
        from app.models_payment import Payment

        q = db.session.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.status == "captured",
        )
        paid_min = sum(int(p.minutes or 0) for p in q.all())
    except Exception as e:
        current_app.logger.error("allowance: error leyendo pagos: %s", e)

    allowance_min = free_min + paid_min
    return int(allowance_min * 60)


def _get_used_seconds(user_id: str) -> int:
    try:
        qj = db.session.query(AudioJob).filter(
            AudioJob.user_id == user_id,
            AudioJob.status == "done",
        )
        return sum(int(j.duration_seconds or 0) for j in qj.all())
    except Exception as e:
        current_app.logger.error("used_seconds: error leyendo jobs: %s", e)
        return 0

@bp.route("/jobs", methods=["POST"])
def create_job():
    uid = _require_auth_user_id()
    if not uid:
        return jsonify({"error": "AUTH_REQUIRED"}), 401

    try:
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "Falta archivo"}), 400

        # size sin romper stream
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)

        if MAX_UPLOAD_MB > 0 and size > MAX_UPLOAD_MB * MB:
            return jsonify({"error": f"El archivo supera {MAX_UPLOAD_MB} MB."}), 400

        language_raw = (request.form.get("language") or "auto").strip().lower()
        language = "auto" if language_raw == "auto" else _normalize_lang(language_raw, "en")

        tmpdir = tempfile.mkdtemp(prefix="polyscribe_")
        tmp_path = os.path.join(tmpdir, file.filename)
        file.save(tmp_path)

        dur = _duration_seconds(tmp_path)

        if not dur or dur <= 0:
            return jsonify({"error": "CANNOT_MEASURE_DURATION"}), 400

        allowance_seconds = _get_allowance_seconds(uid)
        used_seconds = _get_used_seconds(uid)
        remain_seconds = max(0, allowance_seconds - used_seconds)

        required_seconds = int(math.ceil(dur))

        if 0 < remain_seconds <= 60:
            _send_usage_email_once(uid, "low_minutes", remain_seconds)

        if required_seconds > remain_seconds:
            _send_usage_email_once(uid, "no_credits", remain_seconds)
            return jsonify(
                {
                    "error": "NO_CREDITS",
                    "required_seconds": required_seconds,
                    "remain_seconds": remain_seconds,
                }
            ), 402

        parts = _prepare_for_openai(tmp_path, OPENAI_FILE_HARD_LIMIT_MB)
        if not parts:
            return jsonify({"error": "No se pudo preparar el audio (falta ffmpeg/archivo muy grande)."}), 400

        transcripts: List[str] = []
        detected_first = ""

        for i, part in enumerate(parts, 1):
            asr = _transcribe_audio(part, language)
            if i == 1:
                detected_first = _normalize_lang(
                    asr.get("language_detected") or language or "und",
                    str(asr.get("language_detected") or "und").strip().lower() or "und",
                )
            transcripts.append(asr.get("transcript", "") or "")

        transcript = "\n".join(t for t in transcripts if t).strip()

        if language == "auto":
            detected_lang, summary = _summarize_auto_robust(transcript, detected_first)
        else:
            detected_lang = _normalize_lang(language, "en")
            summary = _summarize_robust(transcript, detected_lang)

        now = dt.datetime.utcnow()
        job = AudioJob(
            user_id=uid,
            filename=file.filename,
            size_bytes=int(size),
            language=language,
            language_detected=detected_lang,
            status="done" if transcript else "error",
            error_message=None if transcript else "ASR_EMPTY",
            transcript=transcript,
            summary=summary,
            duration_seconds=required_seconds,
            created_at=now,
            updated_at=now,
        )
        db.session.add(job)
        db.session.commit()

        remaining_after_seconds = max(0, allowance_seconds - (used_seconds + required_seconds))

        if 0 < remaining_after_seconds <= 60:
            _send_usage_email_once(uid, "low_minutes", remaining_after_seconds)
        elif remaining_after_seconds <= 0:
            _send_usage_email_once(uid, "no_credits", remaining_after_seconds)

        return jsonify(
            {
                "id": job.id,
                "job_id": job.id,
                "status": job.status,
                "filename": file.filename,
                "language": language,
                "language_detected": detected_lang,
                "transcript": transcript,
                "summary": summary,
            }
        ), 200

    except Exception as e:
        current_app.logger.exception("create_job SERVER_ERROR: %s", e)
        db.session.rollback()
        return jsonify({"error": "SERVER_ERROR"}), 500


@bp.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    uid = _require_auth_user_id()
    if not uid:
        return jsonify({"error": "AUTH_REQUIRED"}), 401

    job = db.session.get(AudioJob, job_id)
    if not job or str(job.user_id) != str(uid):
        return jsonify({"error": "No existe"}), 404

    return jsonify(
        {
            "id": job.id,
            "job_id": job.id,
            "filename": job.filename,
            "language": job.language,
            "language_detected": job.language_detected,
            "transcript": job.transcript or "",
            "summary": job.summary or "",
            "status": job.status,
            "created_at": str(job.created_at),
            "updated_at": str(job.updated_at),
        }
    ), 200


@bp.route("/api/history", methods=["GET"])
def history_api():
    uid = _require_auth_user_id()
    if not uid:
        return jsonify({"error": "AUTH_REQUIRED"}), 401

    limit = max(1, min(200, int(request.args.get("limit", "100"))))
    q = (
        db.session.query(AudioJob)
        .filter(AudioJob.user_id == uid)
        .order_by(AudioJob.created_at.desc())
        .limit(limit)
    )

    items = []
    for r in q.all():
        items.append(
            {
                "id": r.id,
                "job_id": r.id,
                "filename": r.filename or "",
                "language": r.language or "",
                "language_detected": r.language_detected or "",
                "status": r.status or "done",
                "created_at": str(r.created_at),
                "updated_at": str(r.updated_at),
            }
        )

    return jsonify({"items": items}), 200
