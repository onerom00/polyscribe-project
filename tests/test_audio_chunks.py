"""Audio preparation must preserve every chunk, including a short final tail."""
import os
import shutil
import tempfile
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import patch

from app.routes.jobs import _duration_seconds, _split_audio


class AudioChunksTest(unittest.TestCase):
    def test_failed_middle_chunk_rejects_entire_preparation(self):
        with patch("app.routes.jobs._duration_seconds", return_value=3), patch(
            "app.routes.jobs.subprocess.run", side_effect=[
                SimpleNamespace(returncode=0), SimpleNamespace(returncode=1),
            ],
        ) as run, patch("app.routes.jobs.os.path.exists", return_value=True), patch(
            "app.routes.jobs._file_size_mb", return_value=1,
        ):
            self.assertEqual(_split_audio("source", "/tmp", 1), [])
            self.assertEqual(run.call_count, 2)

    def test_invalid_duration_or_chunk_size_is_rejected(self):
        for duration, size in ((0, 1), (float("nan"), 1), (float("inf"), 1), (1, 0), (1, -1)):
            with self.subTest(duration=duration, size=size), patch(
                "app.routes.jobs._duration_seconds", return_value=duration,
            ), patch("app.routes.jobs.subprocess.run") as run:
                self.assertEqual(_split_audio("source", "/tmp", size), [])
                run.assert_not_called()

    def test_empty_output_is_not_a_successful_chunk(self):
        with patch("app.routes.jobs._duration_seconds", return_value=1), patch(
            "app.routes.jobs.subprocess.run", return_value=SimpleNamespace(returncode=0),
        ), patch("app.routes.jobs.os.path.exists", return_value=True), patch(
            "app.routes.jobs._file_size_mb", return_value=0,
        ):
            self.assertEqual(_split_audio("source", "/tmp", 1), [])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools required")
    def test_real_split_preserves_short_final_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "source.wav")
            with wave.open(source, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 32800)  # 2.05 seconds
            parts = _split_audio(source, directory, 1)
            self.assertEqual(len(parts), 3)
            self.assertGreater(_duration_seconds(parts[-1]), 0)
