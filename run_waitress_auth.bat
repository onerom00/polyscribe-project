@echo off
SETLOCAL

REM === Secretos para sesiones local ===
SET "SECRET_KEY=polyscribe_local_dev_secret_2025_09_05"
SET "SECURITY_PASSWORD_SALT=polyscribe_local_salt_2025_09_05"

REM === Waitress con tope 100 MB y tracebacks visibles ===
".\.venv\Scripts\waitress-serve.exe" ^
  --listen=127.0.0.1:8000 ^
  --threads=8 ^
  --channel-timeout=600 ^
  --max-request-body-size=104857600 ^
  --expose-tracebacks ^
  run_auth_wrapper:app

ENDLOCAL

