@echo off
SETLOCAL
set "PAYPAL_ENV=sandbox"
set "PAYPAL_TEST_MODE=1"
set "PAYPAL_CLIENT_ID=PEGA_AQUI_TU_CLIENT_ID_SANDBOX"
set "PAYPAL_SECRET=PEGA_AQUI_TU_SECRET_SANDBOX"
"%~dp0\.venv\Scripts\waitress-serve.exe" ^
  --listen=127.0.0.1:8000 ^
  --threads=8 ^
  --channel-timeout=600 ^
  --max-request-body-size=104857600 ^
  --expose-tracebacks ^
  run_auth_wrapper:app
ENDLOCAL
