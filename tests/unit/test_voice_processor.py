"""Unit tests for VoiceProcessor handling VAD silence stripping, pitch/RMS/WPM acoustic profiling, dual-modal urgency calculation, and VoiceContext generation."""

import os
import tempfile

from router.infrastructure.media.media_validator import MediaValidator
from router.infrastructure.media.voice_processor import VoiceProcessor
from router.infrastructure.media.whisper_integration import WhisperIntegration


def test_voice_processor_urgent_note() -> None:
    validator = MediaValidator()
    whisper = WhisperIntegration()
    processor = VoiceProcessor(validator=validator, whisper_integration=whisper)

    with tempfile.NamedTemporaryFile(suffix=".opus", delete=False) as tmp:
        tmp.write(b"OggS" + b"\x00" * 40000)
        tmp_path = tmp.name

    sidecar = tmp_path + ".txt"
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write("Call me immediately! This is an emergency hospital situation!")

    try:
        voice_ctx = processor.process_voice(
            voice_note_id="vn_202",
            file_path=tmp_path,
            sha256_hash="hash_voice_789",
        )

        assert voice_ctx.voice_note_id == "vn_202"
        assert voice_ctx.duration_seconds >= 0.5
        assert "emergency" in voice_ctx.transcript.lower()
        assert voice_ctx.urgency_score > 0.5
        assert voice_ctx.acoustic_tone in ["URGENT", "NEUTRAL", "SHOUTING"]
        assert len(voice_ctx.speaker_profile) > 0
        assert "wpm" in voice_ctx.speaker_profile
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(sidecar):
            os.remove(sidecar)


def test_voice_processor_calm_note() -> None:
    validator = MediaValidator()
    whisper = WhisperIntegration()
    processor = VoiceProcessor(validator=validator, whisper_integration=whisper)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(b"RIFF" + b"\x00" * 8 + b"WAVE" + b"\x00" * 30000)
        tmp_path = tmp.name

    sidecar = tmp_path + ".txt"
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write("Hey, let us catch up later when you are free.")

    try:
        voice_ctx = processor.process_voice(
            voice_note_id="vn_203",
            file_path=tmp_path,
            sha256_hash="hash_voice_000",
        )

        assert voice_ctx.urgency_score < 0.5
        assert voice_ctx.detected_language == "en"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(sidecar):
            os.remove(sidecar)
