from run_auth_wrapper import app
from app import db
from app.models_job import AudioJob
from datetime import datetime

with app.app_context():
    j = AudioJob(
        user_id=1,
        filename="probe.wav",
        status="done",
        language_detected="es",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(j)
    db.session.commit()
    print("Inserted id:", j.id)
