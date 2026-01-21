from run_auth_wrapper import app
from app import db
from sqlalchemy import text

with app.app_context():
    conn = db.engine.connect()
    rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).fetchall()
    print("Tables:", [r[0] for r in rows])
