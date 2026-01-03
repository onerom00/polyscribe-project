# app/routes/jobs.py
from __future__ import annotations

import os
import re
import math
import tempfile
import datetime as dt
import subprocess
from typing import Optional, Dict, Any, List

from flask import Blueprint, request, jsonify, current_app, session
from app.extensions import db
from app.models import AudioJob

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

bp = Blueprint("jobs", __name__)

_LANG_ALIASES: Dict[str, str] = {
    "es": "es", "spa": "es", "spanish": "es", "es-es": "es",
    "en": "en", "eng": "en", "english": "en", "en-us": "en", "en-gb": "en",
    "pt": "pt", "por": "pt", "portuguese": "pt", "pt-br": "pt", "pt-pt": "pt",
    "fr": "fr", "fra": "fr", "french": "fr",
    "it": "it", "ita": "it", "italian": "it",
    "de": "de", "deu": "de", "german": "de",
    "ca": "ca", "cat": "ca", "catalan": "ca",
    "zh": "zh", "zho": "zh", "chinese": "zh", "zh-cn": "zh",
    "ja": "ja", "jpn": "ja", "japanese": "ja",
    "ko": "ko", "kor": "ko", "korean": "ko",
    "ar": "ar", "ara": "ar", "arabic": "ar",
    "ru": "ru", "rus": "ru", "russian": "ru",
}


def _normalize_lang(code_or_name: Optional[str], default: str = "es") -> str:
    if not code_or_name:
        return default
    s = str(code_or_name).strip().lower().replace("_", "-")
    if s in _LANG_ALIASES:
        return _LANG_ALIASES[s]
    if "-" in s:
        p = s.split("-", 1)[0]
        if p in _LANG_ALIASES:
            return _LANG_ALIASES[p]
    return _LANG_ALIASES.get(s[:2], default)


def _require_auth_user_id() -> str | None:
    """
    Auth PROD: el user_id real viene de la sesión.
    Devuelve string del id (ej: "12") o None si no autenticado.
    """
    uid = session.get("user_id") or session.get("uid")
    if not uid:
        return None
    return str(uid)


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
            [_ffprobe(), "-v", "error", "-show_entries", "format=duration",
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
    if not _client:
        return ""
    system = (
        f"You summarize in {language_code}. "
        "Return 3–6 bullet points. Be abstract. Do not copy phrases."
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
    except Exception:
        return _fallback_extractive_summary(cleaned, 5)


def _transcribe_audio(path: str, language_code: Optional[str]) -> Dict[str, Any]:
    if not _client:
        return {"transcript": "", "language_detected": _normalize_lang(language_code, "es")}

    model = ASR_MODEL or "whisper-1"
    lang = None if (not language_code or language_code == "auto") else _normalize_lang(language_code, "es")

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
            current_app.logger.warning("ASR failed: %s", e)
            return {"transcript": "", "language_detected": _normalize_lang(lang or "es", "es")}


def _get_allowance_seconds(user_id: str) -> int:
    free_min = int(current_app.config.get("FREE_TIER_MINUTES", 10))

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

        # size (sin romper stream)
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

        # En PROD: si no se puede medir, bloqueamos (para cobrar serio)
        if not dur or dur <= 0:
            return jsonify({"error": "CANNOT_MEASURE_DURATION"}), 400

        # Bloqueo real por créditos
        allowance_seconds = _get_allowance_seconds(uid)
        used_seconds = _get_used_seconds(uid)
        remain_seconds = max(0, allowance_seconds - used_seconds)

        required_seconds = int(math.ceil(dur))
        if required_seconds > remain_seconds:
            return jsonify({
                "error": "NO_CREDITS",
                "required_seconds": required_seconds,
                "remain_seconds": remain_seconds,
            }), 402

        parts = _prepare_for_openai(tmp_path, OPENAI_FILE_HARD_LIMIT_MB)
        if not parts:
            return jsonify({"error": "No se pudo preparar el audio (falta ffmpeg/archivo muy grande)."}), 400

        transcripts: List[str] = []
        detected_first = ""

        for i, part in enumerate(parts, 1):
            asr = _transcribe_audio(part, language)
            if i == 1:
                detected_first = _normalize_lang(asr.get("language_detected") or language or "es", "es")
            transcripts.append(asr.get("transcript", "") or "")

        transcript = "\n".join(t for t in transcripts if t).strip()
        detected_lang = detected_first if language == "auto" else _normalize_lang(language, "en")
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
