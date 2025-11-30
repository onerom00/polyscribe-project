# run_auth_wrapper.py
import logging
from app import create_app

# Configuración básica de logs
logging.basicConfig(
    level=logging.INFO,  # Mínimo nivel que se mostrará
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

app = create_app()
