@echo off
REM Genera requirements.txt desde tu venv actual y hace un backup de la carpeta.
CALL .\.venv\Scripts\activate
pip freeze > requirements.txt
set dt=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
set dt=%dt: =0%
mkdir C:\Backups\polyscribe-%dt%
xcopy /E /I /Y C:\Users\Casa\Documents\polyscribe-project C:\Backups\polyscribe-%dt%\
echo Hecho: requirements.txt y backup a C:\Backups\polyscribe-%dt%\
