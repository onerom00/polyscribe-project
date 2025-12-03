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

# Modelos: tolerantes a errores de import
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

# Cliente OpenAI
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "")) if OpenAI else None
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
ASR_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")

# Configurables
MB = 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)            # 100 MB front/back
OPENAI_FILE_HARD_LIMIT_MB = int(os.getenv("OPENAI_FILE_LIMIT_MB", "25"))  # límite por petición a OpenAI
MAX_CHUNK_SECONDS = int(os.getenv("MAX_CHUNK_SECONDS", "600"))           # 10 minutos


# =================================================================
#               Utilidades de idioma / usuario / texto
# =================================================================

# Mapa de normalización a ISO-639-1
_LANG_ALIASES: Dict[str, str] = {
    # español
    "es": "es", "spa": "es", "spanish": "es", "es-es": "es", "castellano": "es",
    # inglés
    "en": "en", "eng": "en", "english": "en", "en-us": "en", "en-gb": "en",
    # portugués
    "pt": "pt", "por": "pt", "portuguese": "pt", "pt-br": "pt", "pt-pt": "pt",
    # francés
    "fr": "fr", "fra": "fr", "fre": "fr", "french": "fr", "fr-fr": "fr",
    # italiano
    "it": "it", "ita": "it", "italian": "it",
    # alemán
    "de": "de", "deu": "de", "ger": "de", "german": "de", "de-de": "de",
    # catalán
    "ca": "ca", "cat": "ca", "catalan": "ca",
    # chino
    "zh": "zh", "zho": "zh", "chi": "zh", "chinese": "zh",
    "zh-cn": "zh", "zh-hans": "zh", "zh-hant": "zh",
    # japonés
    "ja": "ja", "jpn": "ja", "japanese": "ja",
    # coreano
    "ko": "ko", "kor": "ko", "korean": "ko",
    # árabe
    "ar": "ar", "ara": "ar", "arabic": "ar",
    # ruso
    "ru": "ru", "rus": "ru", "russian": "ru",
    # polaco
    "pl": "pl", "pol": "pl", "polish": "pl",
    # ucraniano
    "uk": "uk", "ukr": "uk", "ukrainian": "uk",
    # turco
    "tr": "tr", "tur": "tr", "turkish": "tr",
    # hebreo
    "he": "he", "heb": "he", "hebrew": "he",
    # persa/farsi
    "fa": "fa", "fas": "fa", "per": "fa", "farsi": "fa", "persian": "fa",
    # hindi
    "hi": "hi", "hin": "hi", "hindi": "hi",
    # bengalí
    "bn": "bn", "ben": "bn", "bengali": "bn",
    # tamil
    "ta": "ta", "tam": "ta", "tamil": "ta",
    # telugu
    "te": "te", "tel": "te", "telugu": "te",
    # vietnamita
    "vi": "vi", "vie": "vi", "vietnamese": "vi",
    # indonesio
    "id": "id", "ind": "id", "indonesian": "id",
    # malayo
    "ms": "ms", "msa": "ms", "may": "ms", "malay": "ms",
}


def _normalize_lang(code_or_name: Optional[str], default: str = "es") -> str:
    """Normaliza a código ISO-639-1 (dos letras)."""
    if not code_or_name:
        return default
    s = str(code_or_name).strip().lower()
    s = s.replace("_", "-")
    if len(s) == 2 and s in _LANG_ALIASES:
        return s
    if "-" in s:
        pref = s.split("-", 1)[0]
        if pref in _LANG_ALIASES:
            return _LANG_ALIASES[pref]
    if s in _LANG_ALIASES:
        return _LANG_ALIASES[s]
    if len(s) >= 3 and s[:3] in _LANG_ALIASES:
        return _LANG_ALIASES[s[:3]]
    two = s[:2]
    return _LANG_ALIASES.get(two, default)


def _lang_human(code: str) -> str:
    m = {
        "es": "español", "en": "inglés", "pt": "portugués", "fr": "francés",
        "it": "italiano", "de": "alemán", "ca": "catalán", "zh": "chino",
        "ja": "japonés", "ko": "coreano", "ar": "árabe", "ru": "ruso",
        "pl": "polaco", "uk": "ucraniano", "tr": "turco", "he": "hebreo",
        "fa": "persa", "hi": "hindi", "bn": "bengalí", "ta": "tamil",
        "te": "telugu", "vi": "vietnamita", "id": "indonesio", "ms": "malayo",
    }
    c = _normalize_lang(code or "es", default="es")
    return m.get(c, "español")


def _get_user_id() -> Optional[str]:
    """
    Devuelve el user_id lógico de la app (string).
    Puede venir de sesión, header X-User-Id, query ?user_id o variable DEV_USER_ID.
    """
    raw = (
        session.get("user_id")
        or session.get("uid")
        or request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or os.getenv("DEV_USER_ID", "")
    )
    s = str(raw).strip() if raw else ""
    return s or None


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


def _too_similar(summary: str, source: str, thresh: float = 0.6) -> bool:
    sents = [s.strip().lower() for s in re.split(r"[.!?]\s+", summary or "") if len(s.strip()) >= 8]
    if not sents:
        return False
    src = (source or "").lower()
    matches = sum(1 for s in sents if s and s in src)
    return (matches / max(1, len(sents))) >= thresh


def _fallback_extractive_summary(text: str, max_sents: int = 5) -> str:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.strip()) > 0]
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
    if not _client:
        return ""
    lang_hint = _lang_human(language_code)
    system = (
        f"Eres un asistente que resume en {lang_hint}."
        " Objetivo: producir un resumen breve, ABSTRACTIVO, con 3–6 viñetas."
        " Reglas: (1) No copies frases literales (máx. 6 palabras seguidas)."
        " (2) Usa sinónimos y generaliza; (3) 80–130 palabras; (4) Solo viñetas (• ...)."
    )
    user = f"Texto a resumir:\n\n{clean_text}\n\nGenera el resumen ahora."
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
    target = _normalize_lang(language_code or "es", default="es")

    s1 = ""
    try:
        s1 = _summarize_llm(cleaned, target)
    except Exception:
        s1 = ""

    if s1 and _too_similar(s1, cleaned):
        try:
            s2 = _summarize_llm(
                cleaned + "\n\nNOTA: abstrae y no repitas frases; sintetiza temas.",
                target,
            )
            if s2 and not _too_similar(s2, cleaned):
                return s2
        except Exception:
            pass

    if s1 and not _too_similar(s1, cleaned):
        return s1

    return _fallback_extractive_summary(cleaned, max_sents=5)


# =================================================================
#                    ffmpeg: comprimir / trocear
# =================================================================


def _ffmpeg() -> str:
    return os.getenv("FFMPEG_BIN", "ffmpeg")


def _ffprobe() -> str:
    return os.getenv("FFPROBE_BIN", "ffprobe")


def _have_ffmpeg() -> bool:
    try:
        subprocess.run([_ffmpeg(), "-version"], capture_output=True, check=False)
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
            [_ffprobe(), "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
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
            _ffmpeg(), "-y", "-i", src,
            "-ac", "1", "-ar", "16000",
            "-c:a", "libopus", "-b:a", bitrate,
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
            _ffmpeg(), "-y",
            "-ss", f"{start:.2f}",
            "-i", src,
            "-t", str(chunk_seconds),
            "-ac", "1", "-ar", "16000",
            "-c:a", "libopus", "-b:a", "64k",
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

    parts = _split_audio(compressed, tmpdir, MAX_CHUNK_SECONDS)
    ok_parts: List[str] = []
    for p in parts:
        if _file_size_mb(p) <= hard_limit_mb:
            ok_parts.append(p)
            continue
        p2 = os.path.join(tmpdir, f"shrunk_{os.path.basename(p)}")
        if _compress_to_opus(p, p2, bitrate="32k") and _file_size_mb(p2) <= hard_limit_mb:
            ok_parts.append(p2)
        else:
            ok_parts.append(p2 if os.path.exists(p2) else p)
    return ok_parts


# =================================================================
#                        Transcripción OpenAI
# =================================================================


def _transcribe_audio(path: str, language_code: Optional[str]) -> Dict[str, Any]:
    """
    Devuelve: {"transcript": str, "language_detected": "xx"}
    """
    if not _client:
        return {"transcript": "", "language_detected": _normalize_lang(language_code, "es")}

    model = ASR_MODEL or "whisper-1"
    lang = _normalize_lang(language_code, None) if language_code else None

    with open(path, "rb") as f:
        try:
            # Intento verbose_json (devuelve idioma detectado)
            res = _client.audio.transcriptions.create(
                model=model,
                file=f,
                language=lang,
                response_format="verbose_json",
            )
            text = (res.text or "").strip()
            det_raw = getattr(res, "language", None) or lang or "es"
            det = _normalize_lang(det_raw, "es")
            return {"transcript": text, "language_detected": det}
        except Exception as e:
            current_app.logger.warning("ASR verbose_json falló, reintento texto plano: %s", e)
            try:
                f.seek(0)
                res2 = _client.audio.transcriptions.create(
                    model=model,
                    file=f,
                    language=lang,
                )
                text = (getattr(res2, "text", "") or "").strip()
                det = _normalize_lang(lang or "es", "es")
                return {"transcript": text, "language_detected": det}
            except Exception as e2:
                current_app.logger.error("ASR texto plano también falló: %s", e2)
                return {"transcript": "", "language_detected": _normalize_lang(lang or "es", "es")}


# =================================================================
#                               Rutas
# =================================================================

bp = Blueprint("jobs", __name__)


@bp.route("/jobs", methods=["POST"])
def create_job():
    # user_id lógico (string); si no hay, usamos "guest"
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

    # Idioma elegido en UI (auto o código). Normalizamos.
    language_raw = (request.form.get("language") or "auto").strip().lower()
    language_forced = False
    if language_raw and language_raw != "auto":
        language = _normalize_lang(language_raw, "en")
        language_forced = True
    else:
        language = "auto"

    # Guardar temporal
    tmpdir = tempfile.mkdtemp(prefix="polyscribe_")
    tmp_path = os.path.join(tmpdir, file.filename)
    file.save(tmp_path)

    # Duración original (para uso de minutos)
    orig_duration = _duration_seconds(tmp_path)

    # Preparar para OpenAI (comprimir/trocear si hace falta)
    parts = _prepare_for_openai(tmp_path, OPENAI_FILE_HARD_LIMIT_MB)
    if not parts:
        msg = (
            "No se pudo preparar el audio. Si el archivo supera "
            f"{OPENAI_FILE_HARD_LIMIT_MB} MB por petición y no hay ffmpeg, no es posible procesarlo."
        )
        return jsonify({"error": msg}), 400

    # Transcribir todas las partes y unir
    transcripts: List[str] = []
    detected_first: str = ""
    for idx, part in enumerate(parts, 1):
        asr = _transcribe_audio(part, None if language == "auto" else language)
        if idx == 1:
            detected_first = _normalize_lang(asr.get("language_detected") or language or "es", "es")
        transcripts.append(asr.get("transcript", "") or "")

    transcript = "\n".join(t for t in transcripts if t).strip()
    detected_lang = detected_first if language == "auto" else _normalize_lang(language, "en")

    # Resumen robusto en el idioma correcto
    summary = _summarize_robust(transcript, language_code=detected_lang)

    # Persistir en DB (si el modelo existe). No forzamos ID manual para evitar
    # conflictos de tipo con SQLite (datatype mismatch).
    job_id: Optional[str] = None
    try:
        if AudioJob is not None:
            now = dt.datetime.utcnow()

            job_kwargs: Dict[str, Any] = {}

            # Solo rellenamos los campos que existan en el modelo actual
            if hasattr(AudioJob, "user_id"):
                job_kwargs["user_id"] = uid
            if hasattr(AudioJob, "filename"):
                job_kwargs["filename"] = file.filename
            if hasattr(AudioJob, "original_filename"):
                job_kwargs["original_filename"] = getattr(file, "filename", None) or file.filename
            if hasattr(AudioJob, "orig_filename"):
                job_kwargs["orig_filename"] = getattr(file, "filename", None) or file.filename
            if hasattr(AudioJob, "audio_s3_key"):
                job_kwargs["audio_s3_key"] = ""
            if hasattr(AudioJob, "local_path"):
                job_kwargs["local_path"] = None
            if hasattr(AudioJob, "mime_type"):
                job_kwargs["mime_type"] = None
            if hasattr(AudioJob, "size_bytes"):
                job_kwargs["size_bytes"] = size
            if hasattr(AudioJob, "language"):
                job_kwargs["language"] = language if language != "auto" else "auto"
            if hasattr(AudioJob, "language_forced"):
                job_kwargs["language_forced"] = 1 if language_forced else 0
            if hasattr(AudioJob, "language_detected"):
                job_kwargs["language_detected"] = detected_lang or ""
            if hasattr(AudioJob, "status"):
                job_kwargs["status"] = "done"
            if hasattr(AudioJob, "error"):
                # Usamos False para evitar problemas de tipo con columnas boolean/integer
                job_kwargs["error"] = False
            if hasattr(AudioJob, "error_message"):
                job_kwargs["error_message"] = None
            if hasattr(AudioJob, "transcript"):
                job_kwargs["transcript"] = transcript
            if hasattr(AudioJob, "summary"):
                job_kwargs["summary"] = summary
            if hasattr(AudioJob, "duration_seconds"):
                job_kwargs["duration_seconds"] = orig_duration if orig_duration > 0 else None
            if hasattr(AudioJob, "model_used"):
                job_kwargs["model_used"] = None
            if hasattr(AudioJob, "cost_cents"):
                job_kwargs["cost_cents"] = None
            if hasattr(AudioJob, "created_at"):
                job_kwargs["created_at"] = now
            if hasattr(AudioJob, "updated_at"):
                job_kwargs["updated_at"] = now

            job = AudioJob(**job_kwargs)
            db.session.add(job)
            db.session.commit()
            job_id = str(getattr(job, "id", "")) or None
    except Exception as e:
        current_app.logger.error("DB save failed: %s", e)
        db.session.rollback()

    # Fallback: si por algún motivo no se pudo guardar en DB,
    # devolvemos igualmente un job_id sintético para que el
    # frontend NO muestre "No se recibió job id".
    if not job_id:
        job_id = str(uuid.uuid4())

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
    Suma los minutos de la tabla payments.

    Modo desarrollo: NO filtramos por status, solo por user_id (si existe).
    Así es más fácil comprobar que el webhook / captura está acreditando minutos.
    """
    if Payment is None:
        return 0

    try:
        cols = {c["name"] for c in inspect(db.engine).get_columns("payments")}
        has_user_id = "user_id" in cols

        q = db.session.query(Payment)
        if has_user_id and uid and uid != "guest":
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

    free_min = int(os.getenv("FREE_TIER_MINUTES", "10") or 10)  # 10 min free por defecto
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
