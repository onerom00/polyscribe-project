    class Config:
    ...
    # ==========================
    #  PAYPAL
    # ==========================
    # Modo: sandbox / live
    PAYPAL_MODE = os.getenv("PAYPAL_MODE") or os.getenv("PAYPAL_ENV", "sandbox")
    PAYPAL_ENV = PAYPAL_MODE  # alias para /api/paypal/config

    # Credenciales
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
    PAYPAL_SECRET = os.getenv("PAYPAL_SECRET") or os.getenv("PAYPAL_CLIENT_SECRET")

    # (Opcional) ID de plan si usaras Billing Plans
    PAYPAL_PLAN_ID = os.getenv("PAYPAL_PLAN_ID") or os.getenv("PAYPAL_PLAN_BASIC_ID")

    # Webhook LIVE (el que creamos en PayPal)
    PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")

    # Endpoint base de la API PayPal
    #   - sandbox: https://api-m.sandbox.paypal.com
    #   - live:    https://api-m.paypal.com
    PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")

    # >>>> PRUEBA: forzar habilitado <<<<
    PAYPAL_ENABLED = True   # <- PON ESTO ASÍ, SIN LEER ENV

    # Moneda por defecto para los botones JS
    PAYPAL_CURRENCY = os.getenv("PAYPAL_CURRENCY", "USD")
