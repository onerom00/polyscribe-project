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
from app.models import AudioJob
from app.models_payment import Payment

from sqlalchemy import inspect

# OpenAI
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "")) if OpenAI else None
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
ASR_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")

MB = 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)
OPENAI_FILE_HARD_LIMIT_MB = int(os.getenv("OPENAI_FILE_LIMIT_MB", "25"))
MAX_CHUNK_SECONDS = int(os.getenv("MAX_CHUNK_SECONDS", "600"))
DEV_SKIP_CREDITS = os.getenv("DEV_SKIP_CREDITS", "0") == "1"

bp = Blueprint("jobs", __name__)

_LANG_ALIASES: Dict[str, str] = {
    "es":"es","spa":"es","spanish":"es","es-es":"es","castellano":"es",
    "en":"en","eng":"en","english":"en","en-us":"en","en-gb":"en",
    "pt":"pt","por":"pt","portuguese":"pt","pt-br":"pt","pt-pt":"pt",
    "fr":"fr","fra":"fr","fre":"fr","french":"fr","fr-fr":"fr",
    "it":"it","ita":"it","italian":"it",
    "de":"de","deu":"de","ger":"de","german":"de","de-de":"de",
    "ca":"ca","cat":"ca","catalan":"ca",
    "zh":"zh","zho":"zh","chi":"zh","chinese":"zh","zh-cn":"zh","zh-hans":"zh","zh-hant":"zh",
    "ja":"ja","jpn":"ja","japanese":"ja",
    "ko":"ko","kor":"ko","korean":"ko",
    "ar":"ar","ara":"ar","arabic":"ar",
    "ru":"ru","rus":"ru","russian":"ru",
    "pl":"pl","pol":"pl","polish":"pl",
    "uk":"uk","ukr":"uk","ukrainian":"uk",
    "tr":"tr","tur":"tr","turkish":"tr",
    "he":"he","heb":"he","hebrew":"he",
    "fa":"fa","fas":"fa","per":"fa","farsi":"fa","persian":"fa",
    "hi":"hi","hin":"hi","hindi":"hi",
    "bn":"bn","ben":"bn","bengali":"bn",
    "ta":"ta","tam":"ta","tamil":"ta",
    "te":"te","tel":"te","telugu":"te",
    "vi":"vi","vie":"vi","vietnamese":"vi",
    "id":"id","ind":"id","indonesian":"id",
    "ms":"ms","msa":"ms","may":"ms","malay":"ms",
}


def _normalize_lang(code_or_name: Optional[str], default: str = "es") -> str:
    if not code_or_name:
        return default
    s = str(code_or_name).strip().lower().replace("_", "-")
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
    return _LANG_ALIASES.get(s[:2], default)


def _get_user_id() -> str:
    raw = (
        session.get("user_id")
        or session.get("uid")
        or request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or os.getenv("DEV_USER_ID", "")
    )
    if not raw:
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            data = {}
        raw = data.get("user_id")
    s = str(raw).strip() if raw else ""
    return s or "guest"


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
    if not _client:
        return ""
    system = (
        f"Eres un asistente que resume en {_normalize_lang(language_code,'es')}."
        " Objetivo: producir un resumen ABSTRACTIVO, con 3–6 viñetas."
        " Reglas: no copies frases (máx 6 palabras seguidas), 80–130 palabras, solo viñetas."
    )
    user = f"Texto a resumir:\n\n{clean_text}\n\nGenera el resumen ahora."
    resp = _client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.3,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
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
            s2 = _summarize_llm(cleaned + "\n\nNOTA: abstrae y no repitas frases; sintetiza temas.", target)
            if s2 and not _too_similar(s2, cleaned):
                return s2
        except Exception:
            pass

    if s1 and not _too_similar(s1, cleaned):
        return s1

    return _fallback_extractive_summary(cleaned, max_sents=5)


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
            [_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
            capture_output=True,
            check=False,
        )
        s = (r.stdout.decode(errors="ignore").strip() or "0")
        return float(s)
    except Exception:
        return 0.0


def _compress_to_opus(src: str, dst: str, bitrate: str = "64k") -> bool:
    try:
        cmd = [_ffmpeg(), "-y", "-i", src, "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", bitrate, dst]
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
            _ffmpeg(), "-y", "-ss", f"{start:.2f}", "-i", src, "-t", str(chunk_seconds),
            "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "64k", out,
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
        _compress_to_opus(p, p2, bitrate="32k")
        ok_parts.append(p2 if os.path.exists(p2) else p)
    return ok_parts


def _transcribe_audio(path: str, language_code: Optional[str]) -> Dict[str, Any]:
    if not _client:
        return {"transcript": "", "language_detected": _normalize_lang(language_code, "es")}

    model = ASR_MODEL or "whisper-1"
    lang = _normalize_lang(language_code, "es") if language_code else None

    with open(path, "rb") as f:
        try:
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
                res2 = _client.audio.transcriptions.create(model=model, file=f, language=lang)
                text = (getattr(res2, "text", "") or "").strip()
                det = _normalize_lang(lang or "es", "es")
                return {"transcript": text, "language_detected": det}
            except Exception as e2:
                current_app.logger.error("ASR texto plano también falló: %s", e2)
                return {"transcript": "", "language_detected": _normalize_lang(lang or "es", "es")}


def _minutes_from_payments(uid: str) -> int:
    # Minutos SOLO capturados
    try:
        q = db.session.query(Payment).filter(Payment.user_id == uid, Payment.status == "captured")
        return sum(int(p.minutes or 0) for p in q.all())
    except Exception as e:
        current_app.logger.error("minutes_from_payments failed: %s", e)
        return 0


def _usage_stats(uid: str) -> Dict[str, int]:
    free_min = int(os.getenv("FREE_TIER_MINUTES", "10") or 10)
    paid_min = _minutes_from_payments(uid)
    allowance_seconds = int((free_min + paid_min) * 60)

    used_seconds = 0
    try:
        q = db.session.query(AudioJob).filter(AudioJob.user_id == uid)
        used_seconds = sum(int(j.duration_seconds or 0) for j in q.all())
    except Exception as e:
        current_app.logger.error("usage_stats failed: %s", e)
        used_seconds = 0

    remaining_seconds = max(0, allowance_seconds - used_seconds)
    return {
        "used_seconds": int(used_seconds),
        "allowance_seconds": int(allowance_seconds),
        "remaining_seconds": int(remaining_seconds),
    }


@bp.route("/jobs", methods=["POST"])
def create_job():
    uid = _get_user_id()

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Falta archivo"}), 400

    # Límite de subida
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if MAX_UPLOAD_MB > 0 and size > MAX_UPLOAD_MB * MB:
        return jsonify({"error": f"El archivo supera {MAX_UPLOAD_MB} MB."}), 400

    # Idioma
    language_raw = (request.form.get("language") or "auto").strip().lower()
    language_forced = 0
    if language_raw and language_raw != "auto":
        language = _normalize_lang(language_raw, "en")
        language_forced = 1
    else:
        language = "auto"

    # Guardar temporal
    tmpdir = tempfile.mkdtemp(prefix="polyscribe_")
    tmp_path = os.path.join(tmpdir, file.filename)
    file.save(tmp_path)

    orig_duration = _duration_seconds(tmp_path)

    # Control de créditos
    stats = _usage_stats(uid)
    remaining = stats["remaining_seconds"]

    if not DEV_SKIP_CREDITS:
        if orig_duration > 0 and orig_duration > remaining:
            return jsonify({"error": "NO_CREDITS"}), 400

    # Preparar para OpenAI
    parts = _prepare_for_openai(tmp_path, OPENAI_FILE_HARD_LIMIT_MB)
    if not parts:
        msg = (
            "No se pudo preparar el audio (ffmpeg no disponible o archivo demasiado grande para OpenAI). "
            f"Máximo por petición: {OPENAI_FILE_HARD_LIMIT_MB} MB."
        )
        return jsonify({"error": msg}), 400

    # Transcribir y unir
    transcripts: List[str] = []
    detected_first = ""
    for idx, part in enumerate(parts, 1):
        asr = _transcribe_audio(part, None if language == "auto" else language)
        if idx == 1:
            detected_first = _normalize_lang(asr.get("language_detected") or (language if language != "auto" else "es"), "es")
        transcripts.append(asr.get("transcript", "") or "")

    transcript = "\n".join(t for t in transcripts if t).strip()
    detected_lang = detected_first if language == "auto" else _normalize_lang(language, "en")

    summary = _summarize_robust(transcript, language_code=detected_lang) if transcript else ""

    # Guardar en DB SIEMPRE (aunque transcript venga vacío, queda auditado)
    job_id = str(uuid.uuid4())
    now = dt.datetime.utcnow()

    try:
        job = AudioJob(
            id=job_id,
            user_id=uid,
            filename=file.filename,
            original_filename=file.filename,
            audio_s3_key="",
            local_path=None,
            mime_type=None,
            size_bytes=int(size),
            language=(language if language != "auto" else "auto"),
            language_forced=language_forced,
            language_detected=detected_lang or "",
            status="done" if transcript else "error",
            error=0 if transcript else 1,
            error_message=None if transcript else "TRANSCRIPTION_EMPTY",
            transcript=transcript,
            summary=summary,
            duration_seconds=int(orig_duration or 0),
            model_used=ASR_MODEL,
            cost_cents=None,
            created_at=now,
            updated_at=now,
        )
        db.session.add(job)
        db.session.commit()
    except Exception as e:
        current_app.logger.error("DB save failed: %s", e)
        db.session.rollback()

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
    job = db.session.get(AudioJob, job_id)
    if not job:
        return jsonify({"error": "No existe"}), 404

    return jsonify(
        {
            "id": job.id,
            "job_id": job.id,
            "filename": job.filename or "",
            "language": job.language or "",
            "language_detected": job.language_detected or "",
            "transcript": job.transcript or "",
            "summary": job.summary or "",
            "status": job.status or "done",
            "created_at": str(job.created_at or ""),
            "updated_at": str(job.updated_at or ""),
        }
    ), 200


@bp.route("/api/history", methods=["GET"])
def history_api():
    limit = max(1, min(200, int(request.args.get("limit", "100"))))
    uid = _get_user_id()

    items: List[Dict[str, Any]] = []
    try:
        rows = (
            db.session.query(AudioJob)
            .filter(AudioJob.user_id == uid)
            .order_by(AudioJob.created_at.desc())
            .limit(limit)
            .all()
        )
        for r in rows:
            items.append(
                {
                    "id": r.id,
                    "job_id": r.id,
                    "filename": r.filename or "",
                    "language": r.language or "",
                    "language_detected": r.language_detected or "",
                    "status": r.status or "done",
                    "created_at": str(r.created_at or ""),
                    "updated_at": str(r.updated_at or ""),
                }
            )
    except Exception as e:
        current_app.logger.exception("history query failed: %s", e)

    return jsonify({"items": items}), 200
