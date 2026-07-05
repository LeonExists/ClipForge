"""Transcription lane: word-timestamped transcripts behind a swappable interface."""

from clipforge.transcribe.base import Segment, Transcriber, Transcript, Word
from clipforge.transcribe.factory import get_transcriber

__all__ = ["Word", "Segment", "Transcript", "Transcriber", "get_transcriber"]
