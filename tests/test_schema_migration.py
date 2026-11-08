"""Exercise the additive revision against a disposable test database."""
import os
import tempfile
import unittest
from unittest.mock import patch

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, stamp, upgrade
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db
from app.models import AudioJob


class SchemaMigrationTest(unittest.TestCase):
    def test_upgrade_downgrade_preserves_existing_job(self):
        with tempfile.TemporaryDirectory() as directory:
            uri = os.getenv("POLYSCRIBE_TEST_DATABASE_URL", f"sqlite:///{directory}/migration.db")
            with patch.dict(os.environ, {
                "DATABASE_URL": uri, "OPENAI_API_KEY": "local-test-placeholder",
            }):
                app = create_app()
            with app.app_context():
                try:
                    tables = [table for table in db.metadata.sorted_tables
                              if table.name not in {"transcription_runs", "transcript_segments"}]
                    db.metadata.create_all(db.engine, tables=tables)
                    stamp(revision="0e9c61264114")
                    job = AudioJob(user_id="migration-test", transcript="Existing transcript")
                    db.session.add(job)
                    db.session.commit()
                    job_id = job.id
                    # Release read transactions before DDL takes PostgreSQL locks.
                    db.session.remove()
                    upgrade(revision="b7d2a8e41001")
                    with db.engine.connect() as connection:
                        self.assertEqual(compare_metadata(
                            MigrationContext.configure(connection), db.metadata,
                        ), [])
                    self.assertEqual(db.session.get(AudioJob, job_id).transcript, "Existing transcript")
                    db.session.remove()
                    downgrade(revision="0e9c61264114")
                    self.assertNotIn("transcription_runs", inspect(db.engine).get_table_names())
                    self.assertNotIn("transcript_segments", inspect(db.engine).get_table_names())
                    upgrade(revision="b7d2a8e41001")
                    self.assertEqual(db.session.get(AudioJob, job_id).transcript, "Existing transcript")
                finally:
                    db.session.remove()
                    db.drop_all()
                    with db.engine.begin() as connection:
                        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
