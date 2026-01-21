# run_waitress.py
# Ejecuta tu app Flask con Waitress en Windows sin tocar tu código.
# Primero intenta app.create_app(); si no existe, usa main.app.

from waitress import serve

def load_app():
    # Opción A: factory create_app()
    try:
        from app import create_app  # si tu proyecto usa factory
        return create_app()
    except Exception:
        pass
    # Opción B: objeto "app" expuesto en main.py
    try:
        from main import app
        return app
    except Exception as e:
        raise RuntimeError(
            "No pude encontrar la aplicación Flask.\n"
            "Intenté: app.create_app() y main.app.\n"
            f"Detalle: {e}"
        )

if __name__ == "__main__":
    application = load_app()
    print("[Waitress] Sirviendo en http://127.0.0.1:8000 (producción Windows)")
    serve(application, listen="127.0.0.1:8000", threads=8)
