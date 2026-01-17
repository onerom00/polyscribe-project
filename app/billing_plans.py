# app/billing_plans.py
import os

# Mapea plan_id de PayPal → (tier, minutos_por_ciclo)
# ⚠️ Reemplaza P-XXXX... por tus IDs reales desde el dashboard de PayPal
PLAN_MAP = {
    "P-XXXXBASIC": ("basic", 120),     # 2 horas / ciclo
    "P-XXXXPRO__": ("pro", 600),       # 10 horas / ciclo
    "P-XXXXUNL__": ("unlimited", 10_000_000),  # “ilimitado”
}

# Duración del ciclo en días (31 por defecto)
DEFAULT_CYCLE_DAYS = int(os.getenv("BILLING_CYCLE_DAYS", "31"))
