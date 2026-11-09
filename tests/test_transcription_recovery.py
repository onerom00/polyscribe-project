"""Recovery tests against the existing production schema, without paid calls."""
import io
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from openai import AuthenticationError, RateLimitError
from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import AudioJob
from app.models_user import User
from app.services.asr_errors import classify_asr_error, normalize_api_key


def rate_error(code="rate_limit_exceeded"):
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions"))
    return RateLimitError("fixture", response=response, body={"code": code})


class TranscriptionRecoveryTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "DATABASE_URL": os.getenv("POLYSCRIBE_TEST_DATABASE_URL", "sqlite:///:memory:"),
            "OPENAI_API_KEY": "local-test-placeholder", "FREE_TIER_MINUTES": "5",
        })
        env.start()
        self.addCleanup(env.stop)
        self.app = create_app()
        self.app.config.update(TESTING=True, SESSION_COOKIE_DOMAIN=None, SESSION_COOKIE_SECURE=False)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(email="recovery@example.invalid", is_verified=True, is_active=True)
        db.session.add(user)
        db.session.commit()
        self.uid = str(user.id)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = self.uid
        self.provider = Mock()
        self.provider.audio.transcriptions.create.return_value = SimpleNamespace(text="Texto.", language="spanish")
        self.provider.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"language":"es","summary":["Resumen"]}')),
        ])

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def upload(self, parts=1):
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            audio = str(Path(directory) / "part.wav")
            Path(audio).write_bytes(b"fixture")
            with patch("app.routes.jobs._client", self.provider), patch(
                "app.routes.jobs._duration_seconds", return_value=1,
            ), patch("app.routes.jobs._prepare_for_openai", return_value=[audio] * parts), patch(
                "app.routes.jobs.tempfile.mkdtemp", return_value=directory,
            ), patch("app.routes.jobs._send_usage_email_once"):
                return self.client.post("/jobs", data={
                    "file": (io.BytesIO(b"fixture"), "sample.wav"), "language": "auto",
                })

    def test_success_uses_existing_schema_and_consumes_duration_once(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "done")
        self.assertEqual(response.json["transcript"], "Texto.")
        self.assertEqual(self.client.get("/api/usage/balance").json["used_seconds"], 1)
        self.assertNotIn("transcription_runs", inspect(db.engine).get_table_names())

    def test_insufficient_quota_is_recorded_without_consumption(self):
        self.provider.audio.transcriptions.create.side_effect = rate_error("insufficient_quota")
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"], "ASR_QUOTA_EXCEEDED")
        self.assertIn("minutos se conservan", response.json["message"])
        self.assertEqual(db.session.query(AudioJob).one().error_message, "ASR_QUOTA_EXCEEDED")
        self.assertEqual(self.client.get("/api/usage/balance").json["used_seconds"], 0)
        self.provider.chat.completions.create.assert_not_called()

    def test_rate_limit_is_distinct_from_insufficient_quota(self):
        self.provider.audio.transcriptions.create.side_effect = rate_error()
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"], "ASR_RATE_LIMITED")

    def test_partial_transcript_is_not_marked_done(self):
        self.provider.audio.transcriptions.create.side_effect = [
            SimpleNamespace(text="Partial", language="en"), rate_error("insufficient_quota"),
        ]
        response = self.upload(parts=3)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["transcript"], "")
        self.assertEqual(self.provider.audio.transcriptions.create.call_count, 2)
        self.assertEqual(self.client.get("/api/usage/balance").json["used_seconds"], 0)

    def test_empty_transcript_is_not_success(self):
        self.provider.audio.transcriptions.create.return_value = SimpleNamespace(text="", language="en")
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"], "ASR_EMPTY")

    def test_legacy_failed_jobs_are_not_in_displayed_usage(self):
        db.session.add_all([
            AudioJob(user_id=self.uid, status="error", duration_seconds=78),
            AudioJob(user_id=self.uid, status="done", duration_seconds=10),
        ])
        db.session.commit()
        self.assertEqual(self.client.get("/api/usage/balance").json["used_seconds"], 10)

    def test_error_classification_does_not_leak_response_body(self):
        response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com"))
        exc = AuthenticationError("private response fixture", response=response, body={})
        self.assertEqual(classify_asr_error(exc), "ASR_AUTH_ERROR")

    def test_missing_or_malformed_credentials_are_rejected(self):
        self.assertIsNone(normalize_api_key(""))
        self.assertIsNone(normalize_api_key("Bearer fixture"))
        self.assertIsNone(normalize_api_key("fixture\nkey"))
        self.assertEqual(normalize_api_key(" fixture\n"), "fixture")

    def test_guest_upload_is_rejected(self):
        response = self.app.test_client().post("/jobs")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(db.session.query(AudioJob).count(), 0)
