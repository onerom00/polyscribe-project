# run_auth_wrapper.py
import logging
import os
from app import create_app

# Configuración básica de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

app = create_app()

if os.getenv("APP_DEBUG_TRACE", "0") == "1":
    app.config["PROPAGATE_EXCEPTIONS"] = True
