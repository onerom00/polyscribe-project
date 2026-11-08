"""Bootstrap ONLY a new disposable staging database, never production."""
import os
import httpx

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import stamp, upgrade
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models_user import User
from app.services.transcription_provider import normalize_api_key


def prepare_staging():
    if os.getenv("POLYSCRIBE_STAGING") != "1":
        raise RuntimeError("Staging bootstrap requires POLYSCRIBE_STAGING=1")
    password = os.getenv("STAGING_TEST_PASSWORD", "")
    email = os.getenv("STAGING_TEST_EMAIL", "").strip().lower()
    if len(password) < 16 or not email.endswith("@example.invalid"):
        raise RuntimeError("A generated staging password and example.invalid account are required")
    app = create_app()
    with app.app_context():
        if db.engine.dialect.name != "postgresql" or db.engine.url.database != "polyscribe_staging":
            raise RuntimeError("Bootstrap only accepts the dedicated polyscribe_staging PostgreSQL database")
        tables = inspect(db.engine).get_table_names()
        if not tables:
            # Historical revisions assume an existing schema. Build their current
            # baseline explicitly, then exercise the additive One revision.
            baseline = [table for table in db.metadata.sorted_tables
                        if table.name not in {"transcription_runs", "transcript_segments"}]
            db.metadata.create_all(db.engine, tables=baseline)
            stamp(revision="0e9c61264114")
        elif "alembic_version" not in tables:
            raise RuntimeError("Refusing to stamp a non-empty, unversioned database")
        upgrade(revision="b7d2a8e41001")
        with db.engine.connect() as connection:
            if compare_metadata(MigrationContext.configure(connection), db.metadata):
                raise RuntimeError("Staging schema differs from the application models")
        user = db.session.query(User).filter_by(email=email).first()
        if user is None:
            user = User(email=email, is_active=True, is_verified=True)
            db.session.add(user)
        user.password_hash = generate_password_hash(password)
        db.session.commit()
    print("Dedicated staging schema and test account ready")
    key_ready = normalize_api_key(os.getenv("OPENAI_API_KEY", "")) is not None
    print(f"Staging OpenAI credential format configured: {key_ready}")
    # Unauthenticated probe: no API key, audio or billable model invocation.
    try:
        response = httpx.get("https://api.openai.com/v1/models", timeout=10)
        print(f"Staging OpenAI connectivity probe HTTP {response.status_code}")
    except Exception as exc:
        causes = []
        cause = exc
        for _ in range(6):
            if cause is None:
                break
            causes.append(type(cause).__name__)
            cause = cause.__cause__ or cause.__context__
        print("Staging OpenAI connectivity probe failed: " + ">".join(causes))


if __name__ == "__main__":
    prepare_staging()
