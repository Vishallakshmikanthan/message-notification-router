"""Unit tests for WhisperIntegration speech-to-text transcription and timestamp alignment."""

import os
import tempfile

from router.infrastructure.media.whisper_integration import WhisperIntegration


def test_whisper_transcription() -> None:
    whisper = WhisperIntegration()
    with tempfile.NamedTemporaryFile(suffix=".opus", delete=False) as tmp:
        tmp.write(b"dummy audio content")
        tmp_path = tmp.name

    try:
        payload = whisper.transcribe_audio(tmp_path)
        assert "transcript" in payload
        assert payload["transcript_confidence"] > 0.8
        assert payload["detected_language"] == "en"
        assert len(payload["word_timestamps"]) > 0
        assert payload["word_timestamps"][0].start_ms >= 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_whisper_sidecar_override() -> None:
    whisper = WhisperIntegration()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(b"audio data")
        tmp_path = tmp.name

    sidecar = tmp_path + ".txt"
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write("Call me immediately at the office.")

    try:
        payload = whisper.transcribe_audio(tmp_path)
        assert payload["transcript"] == "Call me immediately at the office."
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(sidecar):
            os.remove(sidecar)
