@echo off
SETLOCAL
REM === Modo prueba de planes (activa endpoint simulado) ===
SET PAYPAL_TEST_MODE=1

REM Activa el virtualenv
CALL "%~dp0\.venv\Scripts\activate"

REM Sirve la app (con tope 100 MB)
waitress-serve --listen=127.0.0.1:8000 --threads=8 --channel-timeout=600 --max-request-body-size=104857600 run_auth_wrapper:app

ENDLOCAL

