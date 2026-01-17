# app/job_processor.py
import os, logging, time, math
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AudioJob, User, JobStatus

log = logging.getLogger(__name__)

def _minutes_from_seconds(sec: Optional[float]) -> int:
    if not sec or sec <= 0:
        return 1
    return max(1, math.ceil(sec / 60.0))

def _charge_minutes(user: User, seconds: Optional[float]) -> None:
    user.minutes_used = int(user.minutes_used or 0) + _minutes_from_seconds(seconds or 60)

def _summarize_openai(text: str, lang: str | None) -> str:
    # SDK “nuevo” de OpenAI
    try:
        from openai import OpenAI
        client = OpenAI()
        prompt = (
            "Resume con 5–8 líneas claras. Devuelve sólo el resumen.\n\n"
            f"Idioma objetivo: {lang or 'es'}.\n\nTexto:\n{text[:12000]}"
        )
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini"),
            messages=[{"role":"user","content":prompt}],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        log.exception("Fallo resumiendo con OpenAI: %s", e)
        return ""

def _transcribe_openai(filepath: str, lang_hint: str | None):
    # Devuelve (texto, idioma_detectado, dur_seconds)
    from openai import OpenAI
    client = OpenAI()
    with open(filepath, "rb") as f:
        tr = client.audio.transcriptions.create(
            model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
            file=f,
            language=(lang_hint or None),          # puede ser None
            response_format="verbose_json",
            temperature=0
        )
    text = tr.text or ""
    lang = getattr(tr, "language", None) or (lang_hint or None)
    dur = getattr(tr, "duration", None)  # algunos SDKs lo traen; si no, None
    try:
        dur = float(dur) if dur is not None else None
    except Exception:
        dur = None
    return text, lang, dur

def process_job_now(job_id: int, mode: str = "auto") -> None:
    """
    Procesa un job:
      - mode="auto": usa OpenAI si hay OPENAI_API_KEY; si no, demo.
      - mode="demo": fuerza demo (útil para pruebas).
      - mode="openai": fuerza OpenAI; si falla, marca error.
    """
    db: Session = SessionLocal()
    j = None
    try:
        j = db.query(AudioJob).get(job_id)
        if not j:
            log.warning("Job %s no existe", job_id); return
        u = db.query(User).get(j.user_id)
        if not u:
            log.warning("Usuario %s no existe", j.user_id); return

        j.status = JobStatus.processing
        db.commit()

        use_openai = (os.getenv("OPENAI_API_KEY") and (mode in ("auto","openai")))
        transcript = ""; language = j.language_forced or "es"; duration = None

        if use_openai:
            transcript, language, duration = _transcribe_openai(j.local_path, j.language_forced)
        elif mode == "openai":
            raise RuntimeError("OPENAI_API_KEY no configurada.")

        if not transcript:
            # DEMO como fallback
            transcript = f"[DEMO-real] Transcripción simulada de {j.original_filename or os.path.basename(j.local_path or '')}."
            language = language or "es"

        # Guardar transcripción
        j.transcript = transcript
        j.language_detected = language

        # Resumen
        summary = ""
        if use_openai and transcript.strip():
            summary = _summarize_openai(transcript, language)
        if not summary:
            summary = "[DEMO] Resumen simulado."

        if hasattr(j, "summary"):
            try:
                setattr(j, "summary", summary)
            except Exception:
                pass
        if hasattr(j, "summary_json"):
            j.summary_json = {"summary": summary}

        j.status = JobStatus.done

        # Cobro de minutos (aprox por duración; si no hay, 1 min)
        _charge_minutes(u, duration)

        db.commit()
        log.info("Job %s completado (%s)", j.id, "openai" if use_openai else "demo")
    except Exception as e:
        log.exception("Fallo procesando job %s: %s", job_id, e)
        try:
            if j:
                j.status = JobStatus.error
                j.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
