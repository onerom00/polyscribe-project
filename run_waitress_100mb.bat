@echo off
REM ===========================
REM PolyScribe - Waitress (Windows)
REM Producción local con tope de 100 MB por request
REM ===========================

SETLOCAL
CALL .\.venv\Scripts\activate

REM === Elige UNO de los dos lanzadores (deja descomentado el que corresponda) ===
REM Opción A: tu app expone "app" en main.py (lo más común porque ejecutas "python main.py")
waitress-serve --listen=127.0.0.1:8000 --threads=8 --channel-timeout=600 --max-request-body-size=104857600 main:app

REM Opción B: si usas factory create_app() en app/__init__.py, comenta la línea de arriba
REM y descomenta esta:
REM waitress-serve --listen=127.0.0.1:8000 --threads=8 --channel-timeout=600 --max-request-body-size=104857600 --call app:create_app

ENDLOCAL
