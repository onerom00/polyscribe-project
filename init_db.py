from run_auth_wrapper import app
from app import db
# Importa modelos para registrarlos en metadata:
try:
    from app.models_user import User
except Exception as e:
    print("No pude importar User:", e)
try:
    from app.models_job import AudioJob
except Exception:
    pass
try:
    from app.models_payment import Payment
except Exception:
    pass

from sqlalchemy import inspect
with app.app_context():
    db.create_all()
    insp = inspect(db.engine)
    print("Tablas ahora:", insp.get_table_names())
