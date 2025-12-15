# app/models/__init__.py
# Hace que app.models sea el punto único de importación de modelos.

from .audio_job import AudioJob

__all__ = ["AudioJob"]
