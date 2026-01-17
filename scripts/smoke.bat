:: scripts\smoke.bat
@echo off
copy /Y "C:\Windows\Media\ding.wav" test.wav >NUL

curl.exe -s -F "audio=@test.wav" -F "idioma=es" http://127.0.0.1:5000/jobs > resp.json
for /f %%A in ('py -c "import json;print(json.load(open(''resp.json''))[''job_id''])"') do set JOB_ID=%%A

if "%JOB_ID%"=="" (
  echo No se pudo crear el job:
  type resp.json
  exit /b 1
)

echo JOB=%JOB_ID%
for /l %%i in (1,1,10) do (
  timeout /t 2 >NUL
  curl.exe -s http://127.0.0.1:5000/jobs/%JOB_ID% > status.json
  for /f "usebackq delims=" %%L in ("status.json") do echo %%L
)
