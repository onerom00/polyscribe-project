# run-dev.ps1
$ErrorActionPreference = "Stop"
python -m pip install -r requirements.txt
python scripts/doctor.py
$env:FLASK_DEBUG="1"
python .\main.py
