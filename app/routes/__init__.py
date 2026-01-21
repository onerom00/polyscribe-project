# app/routes/__init__.py
from __future__ import annotations

def register_routes(app):
    # Importa y registra blueprints aquí para evitar imports circulares

    from app.routes.jobs import bp as jobs_bp
    app.register_blueprint(jobs_bp)

    # (si ya tienes history/pricing/paypal/etc, agrega igual)
    try:
        from app.routes.history import bp as history_bp
        app.register_blueprint(history_bp)
    except Exception:
        pass

    try:
        from app.routes.paypal import bp as paypal_bp
        app.register_blueprint(paypal_bp)
    except Exception:
        pass

    # ✅ NUEVO: leads
    from app.routes.leads import bp as leads_bp
    app.register_blueprint(leads_bp)
