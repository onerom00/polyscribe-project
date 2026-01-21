# wsgi_paypal_env.py
import os, pathlib

def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            # solo establece si no está ya en el entorno
            os.environ.setdefault(k.strip(), v.strip())

ROOT = pathlib.Path(__file__).resolve().parent
ENV_FILE = ROOT / "instance" / "paypal.env"
load_env(str(ENV_FILE))

# defaults seguros
os.environ.setdefault("PAYPAL_ENV", "sandbox")
os.environ.setdefault("PAYPAL_TEST_MODE", "1")

# AHORA importamos la app (los blueprints leerán las vars que acabamos de poner)
from run_auth_wrapper import app  # noqa: E402
