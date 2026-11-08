"""Provider boundary for timed transcription; no billing or database writes."""
from dataclasses import dataclass, field
import math
import time
from typing import Any


def normalize_api_key(value: str) -> str | None:
    """Reject malformed HTTP credentials without disclosing their contents."""
    value = value.strip()
    if not value or any(ord(char) < 33 or ord(char) > 126 for char in value):
        return None
    return value


@dataclass
class ProviderSegment:
    start: float
    end: float
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ProviderResult:
    text: str
    language: str | None
    segments: list[ProviderSegment]
    latency_ms: int


class OpenAITranscriptionProvider:
    name = "openai"

    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    def transcribe(self, path: str, language: str | None) -> ProviderResult:
        started = time.monotonic()
        with open(path, "rb") as audio:
            response = self.client.audio.transcriptions.create(
                model=self.model, file=audio, language=language,
                response_format="verbose_json",
            )
        segments = []
        for segment in getattr(response, "segments", None) or []:
            value = segment if isinstance(segment, dict) else segment.model_dump()
            start, end = float(value["start"]), float(value["end"])
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
                raise ValueError("Provider returned invalid segment timestamps")
            # Log probabilities are preserved as metadata, never invented confidence.
            metadata = {key: value[key] for key in (
                "avg_logprob", "no_speech_prob", "compression_ratio",
            ) if value.get(key) is not None}
            segments.append(ProviderSegment(start, end, value.get("text", ""), metadata))
        return ProviderResult(
            text=(response.text or "").strip(),
            language=getattr(response, "language", None),
            segments=segments,
            latency_ms=max(0, round((time.monotonic() - started) * 1000)),
        )
