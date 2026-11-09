"""Stable provider error categories; never expose provider bodies or credentials."""


def normalize_api_key(value: str) -> str | None:
    value = value.strip()
    if not value or any(ord(char) < 33 or ord(char) > 126 for char in value):
        return None
    return value


def classify_asr_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    if code == "insufficient_quota":
        return "ASR_QUOTA_EXCEEDED"
    if status == 429:
        return "ASR_RATE_LIMITED"
    if status == 401:
        return "ASR_AUTH_ERROR"
    if status == 403:
        return "ASR_ACCESS_DENIED"
    if type(exc).__name__ in {"APIConnectionError", "APITimeoutError"}:
        return "ASR_CONNECTION_ERROR"
    return "ASR_FAILED"
