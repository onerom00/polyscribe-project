from run_auth_wrapper import app
from app import db
from app.models_usage import UsageLedger  # registra el modelo en metadata

with app.app_context():
    db.create_all()
    print("OK create_all ->", db.inspect(db.engine).get_table_names())
