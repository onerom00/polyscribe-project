@echo off
REM Backup ligero de PolyScribe (excluye folders pesados)
set SRC=C:\Users\Casa\Documents\polyscribe-project
set DESTROOT=C:\Backups

REM Timestamp robusto independiente del idioma:
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set STAMP=%%i

set DEST=%DESTROOT%\polyscribe-%STAMP%
mkdir "%DEST%" 2>nul

REM Guardar requirements del venv actual
call "%SRC%\.venv\Scripts\activate" 2>nul
pip freeze > "%SRC%\requirements.txt"

REM Copia con ROBOCOPY excluyendo carpetas pesadas
robocopy "%SRC%" "%DEST%" /E ^
 /XD uploads .venv __pycache__ logs ^
 /XF *.pyc *.log

echo.
echo Backup ligero creado en: %DEST%
echo (excluye uploads, .venv, __pycache__, logs)
