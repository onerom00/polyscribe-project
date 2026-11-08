"""Persistence checks using only an isolated in-memory database."""
import os
import io
import unittest
from unittest.mock import patch, Mock

from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import AudioJob, TranscriptSegment, TranscriptionRun
from app.services.transcription_provider import ProviderSegment, OpenAITranscriptionProvider


class TranscriptionModelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {
            "DATABASE_URL": os.getenv("POLYSCRIBE_TEST_DATABASE_URL", "sqlite:///:memory:"),
            "OPENAI_API_KEY": "local-test-placeholder",
        }):
            cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        # SQLite does not enforce foreign keys unless explicitly enabled.
        if db.engine.dialect.name == "sqlite":
            @event.listens_for(db.engine, "connect")
            def enable_foreign_keys(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
        db.create_all()
        self.job = AudioJob(user_id="local-user", transcript="Legacy text")
        db.session.add(self.job)
        db.session.flush()
        self.run = TranscriptionRun(job=self.job, provider="test", model="test-model")
        db.session.add(self.run)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def segment(self, **overrides):
        values = dict(transcription_run_id=self.run.id, sequence=0,
                      start_seconds=1.25, end_seconds=2.5, text="Evidence")
        values.update(overrides)
        return TranscriptSegment(**values)

    def test_round_trip_and_legacy_result(self):
        db.session.add_all([
            self.segment(sequence=1, speaker="Speaker 2", confidence=0.94),
            self.segment(sequence=0, raw_metadata={"source": "test"}),
        ])
        db.session.commit()
        db.session.expire_all()
        self.assertEqual([s.sequence for s in self.run.segments], [0, 1])
        self.assertEqual(self.run.segments[0].raw_metadata, {"source": "test"})
        self.assertEqual(self.run.job.transcript, "Legacy text")
        self.assertIsNone(self.run.overall_confidence)
        self.assertFalse(self.run.is_selected)

    def test_duplicate_sequence_rejected_within_run(self):
        db.session.add_all([self.segment(), self.segment()])
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_sequence_can_repeat_across_runs(self):
        other = TranscriptionRun(job=self.job, provider="other", model="test")
        db.session.add(other)
        db.session.flush()
        db.session.add_all([self.segment(), self.segment(transcription_run_id=other.id)])
        db.session.commit()

    def test_invalid_segments_rejected(self):
        for values in ({"sequence": -1}, {"start_seconds": -1},
                       {"end_seconds": 0}, {"confidence": 1.1},
                       {"confidence": -0.1}, {"transcription_run_id": "missing"}):
            with self.subTest(values=values):
                db.session.add(self.segment(**values))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_invalid_provider_metrics_rejected(self):
        for values in ({"latency_ms": -1}, {"cost_usd": -1},
                       {"language_confidence": 1.1}, {"overall_confidence": -0.1}):
            with self.subTest(values=values):
                db.session.add(TranscriptionRun(
                    job=self.job, provider="test", model="test", **values,
                ))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_only_one_selected_run_per_job(self):
        self.run.is_selected = True
        db.session.commit()
        db.session.add(TranscriptionRun(
            job=self.job, provider="other", model="test", is_selected=True,
        ))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_database_cascade_deletes_run_and_segments(self):
        db.session.add(self.segment())
        db.session.commit()
        db.session.execute(text("DELETE FROM audio_jobs WHERE id = :id"), {"id": self.job.id})
        db.session.commit()
        self.assertEqual(db.session.query(TranscriptionRun).count(), 0)
        self.assertEqual(db.session.query(TranscriptSegment).count(), 0)

    def test_health(self):
        response = self.app.test_client().get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"ok": True})

    def upload(self, results, enabled=True, expected_status=200):
        from contextlib import ExitStack
        self.app.config["POLYSCRIBE_ONE_ENABLED"] = enabled
        self.addCleanup(self.app.config.update, POLYSCRIBE_ONE_ENABLED=False)
        with ExitStack() as stack:
            for name, value in {
                "_require_auth_user_id": "local-user", "_duration_seconds": 30,
                "_get_allowance_seconds": 3600, "_get_used_seconds": 0,
                "_prepare_for_openai": ["unused"] * len(results),
                "_summarize_auto_robust": ("es", "Resumen"),
            }.items():
                stack.enter_context(patch(f"app.routes.jobs.{name}", return_value=value))
            stack.enter_context(patch("app.routes.jobs._transcribe_audio", side_effect=results))
            response = self.app.test_client().post("/jobs", data={
                "file": (io.BytesIO(b"test-audio"), "test.wav"), "language": "auto",
            })
        self.assertEqual(response.status_code, expected_status, response.json)
        return response.json

    def test_upload_persists_timed_result(self):
        result = self.upload([{
            "transcript": "Hola", "language_detected": "es", "latency_ms": 25,
            "segments": [ProviderSegment(0, 2, "Hola", {"avg_logprob": -0.2})],
        }])
        job = db.session.get(AudioJob, result["id"])
        run = db.session.query(TranscriptionRun).filter_by(job_id=job.id).one()
        self.assertEqual(job.transcript, "Hola")
        self.assertEqual(run.transcript_text, "Hola")
        self.assertEqual(run.segments[0].end_seconds, 2)
        self.assertIsNone(run.segments[0].confidence)
        self.assertIsNone(run.cost_usd)
        self.assertTrue(run.is_selected)

    def test_chunk_timestamps_have_global_offsets(self):
        from app.routes.jobs import MAX_CHUNK_SECONDS
        result = self.upload([
            {"transcript": "Uno", "segments": [ProviderSegment(0, 2, "Uno")]},
            {"transcript": "Dos", "segments": [ProviderSegment(1, 3, "Dos")]},
        ])
        run = db.session.query(TranscriptionRun).filter_by(job_id=result["id"]).one()
        self.assertEqual(run.segments[1].start_seconds, MAX_CHUNK_SECONDS + 1)
        self.assertEqual([s.sequence for s in run.segments], [0, 1])

    def test_partial_provider_failure_is_not_billed(self):
        from app.routes.jobs import _get_used_seconds
        result = self.upload([{"transcript": "Partial"}, {"transcript": "", "error": "ASR_FAILED"}], expected_status=502)
        run = db.session.query(TranscriptionRun).filter_by(job_id=result["id"]).one()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["transcript"], "")
        self.assertEqual(_get_used_seconds("local-user"), 0)
        self.assertFalse(run.is_selected)
        self.assertEqual(run.segments, [])
        self.assertEqual(run.error_message, "ASR_FAILED")

    def test_silent_chunk_does_not_discard_valid_speech(self):
        from app.routes.jobs import MAX_CHUNK_SECONDS
        result = self.upload([
            {"transcript": "", "segments": []},
            {"transcript": "Speech", "segments": [ProviderSegment(0, 1, "Speech")]},
        ])
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["transcript"], "Speech")
        run = db.session.query(TranscriptionRun).filter_by(job_id=result["id"]).one()
        self.assertEqual(run.segments[0].start_seconds, MAX_CHUNK_SECONDS)

    def test_disabled_feature_preserves_legacy_upload(self):
        result = self.upload([{"transcript": "Legacy result", "language_detected": "es"}], enabled=False)
        self.assertEqual(result["transcript"], "Legacy result")
        self.assertEqual(db.session.query(TranscriptionRun).filter_by(job_id=result["id"]).count(), 0)

    def test_provider_extracts_segments_without_fabricated_confidence(self):
        client = Mock()
        client.audio.transcriptions.create.return_value = Mock(
            text=" Hola ", language="spanish",
            segments=[{"start": 0, "end": 2, "text": "Hola", "avg_logprob": -0.3}],
        )
        provider = OpenAITranscriptionProvider(client, "whisper-1")
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"test")):
            result = provider.transcribe("test.wav", None)
        self.assertEqual(result.text, "Hola")
        self.assertEqual(result.segments[0].metadata, {"avg_logprob": -0.3})
        self.assertIsNone(client.audio.transcriptions.create.call_args.kwargs["language"])

    def test_provider_rejects_invalid_timestamps(self):
        client = Mock()
        provider = OpenAITranscriptionProvider(client, "whisper-1")
        for start, end in ((-1, 2), (3, 2), (0, float("nan")), (0, float("inf"))):
            client.audio.transcriptions.create.return_value = Mock(
                text="Hola", language="es", segments=[{"start": start, "end": end}],
            )
            with patch("builtins.open", unittest.mock.mock_open(read_data=b"test")):
                with self.assertRaises(ValueError):
                    provider.transcribe("test.wav", "es")


if __name__ == "__main__":
    unittest.main()
