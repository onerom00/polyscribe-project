"""Local upload flow with real auth, duration probing, persistence and balance."""
import io
import os
import shutil
import tempfile
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import create_app
from app.extensions import db
from app.models import AudioJob, TranscriptionRun
from app.models_user import User


@unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is needed for upload flow tests")
class UploadFlowTest(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "DATABASE_URL": os.getenv("POLYSCRIBE_TEST_DATABASE_URL", "sqlite:///:memory:"),
            "OPENAI_API_KEY": "local-test-placeholder", "FREE_TIER_MINUTES": "5",
            "SESSION_COOKIE_DOMAIN": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.app = create_app()
        self.app.config.update(TESTING=True, POLYSCRIBE_ONE_ENABLED=True,
                               SESSION_COOKIE_SECURE=False)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(email="flow@example.invalid", is_verified=True, is_active=True)
        db.session.add(self.user)
        db.session.commit()
        self.uid = str(self.user.id)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = self.uid
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.provider = Mock()
        self.provider.audio.transcriptions.create.return_value = SimpleNamespace(
            text="Texto de prueba.", language="spanish",
            segments=[{"start": 0, "end": 1, "text": "Texto de prueba."}],
        )
        self.provider.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"language":"es","summary":["Resumen de prueba"]}')),
        ])

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def upload(self, client=None):
        audio = io.BytesIO()
        with wave.open(audio, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * 16000)
        audio.seek(0)
        with patch("app.routes.jobs._client", self.provider), patch(
            "app.routes.jobs.tempfile.mkdtemp", return_value=self.directory.name,
        ):
            return (client or self.client).post("/jobs", data={
                "file": (audio, "flow.wav"), "language": "auto",
            })

    def test_success_connects_upload_history_and_balance(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "done")
        self.assertEqual(response.json["language_detected"], "es")
        self.assertIn("Resumen de prueba", response.json["summary"])
        run = db.session.query(TranscriptionRun).one()
        self.assertEqual(run.segments[0].end_seconds, 1)
        self.assertEqual(run.transcript_text, response.json["transcript"])
        history = self.client.get("/api/history").json
        self.assertEqual(history["items"][0]["id"], response.json["id"])
        self.assertEqual(self.client.get("/api/usage/balance").json["used_seconds"], 1)

    def test_real_login_uses_host_only_cookie_on_staging(self):
        from werkzeug.security import generate_password_hash
        password = "local-staging-test-password"
        self.user.password_hash = generate_password_hash(password)
        db.session.commit()
        client = self.app.test_client()
        response = client.post("/auth/login", data={"email": self.user.email, "password": password})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("Domain=", response.headers.get("Set-Cookie", ""))
        self.assertTrue(client.get("/api/usage/balance").json["authenticated"])

    def test_failed_upload_does_not_reduce_displayed_balance(self):
        self.provider.audio.transcriptions.create.side_effect = RuntimeError("simulated failure")
        response = self.upload()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json["status"], "error")
        self.assertIn("No se descontaron minutos", response.json["message"])
        self.assertFalse(db.session.query(TranscriptionRun).one().is_selected)
        self.assertEqual(self.client.get("/api/usage/balance").json["used_seconds"], 0)

    def test_guest_does_not_reach_provider(self):
        response = self.upload(self.app.test_client())
        self.assertEqual(response.status_code, 401)
        self.provider.audio.transcriptions.create.assert_not_called()
        self.assertEqual(db.session.query(AudioJob).count(), 0)

    def test_exhausted_balance_does_not_reach_provider(self):
        db.session.add(AudioJob(user_id=self.uid, status="done", duration_seconds=300))
        db.session.commit()
        # Avoid SMTP: the credit rejection itself is exercised normally.
        with patch("app.routes.jobs._send_usage_email_once"):
            response = self.upload()
        self.assertEqual(response.status_code, 402)
        self.provider.audio.transcriptions.create.assert_not_called()
        self.assertEqual(db.session.query(TranscriptionRun).count(), 0)

    def test_other_user_cannot_read_job(self):
        response = self.upload()
        other = User(email="other@example.invalid", is_active=True, is_verified=True)
        db.session.add(other)
        db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = str(other.id)
        self.assertEqual(client.get(f'/jobs/{response.json["id"]}').status_code, 404)
        self.assertEqual(client.get("/api/history").json["items"], [])
        self.assertEqual(client.get("/api/usage/balance").json["used_seconds"], 0)
