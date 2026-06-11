"""Unit tests for the Nemotron quality-gate helpers added to main.py.

These tests only exercise pure-Python helpers (no model load, no inference).
They import `main` lazily and skip if heavy ASR deps aren't installed in
the test environment.
"""
from __future__ import annotations

import pytest

main = pytest.importorskip("main")


class _FakeHyp:
    def __init__(self, score=None, y_sequence=None):
        if score is not None:
            self.score = score
        if y_sequence is not None:
            self.y_sequence = y_sequence


def test_avg_logprob_normal():
    hyp = _FakeHyp(score=-5.0, y_sequence=[1, 2, 3, 4, 5])
    assert main._nemotron_avg_logprob(hyp) == pytest.approx(-1.0)


def test_avg_logprob_missing_fields_returns_neutral():
    assert main._nemotron_avg_logprob(None) == 0.0
    assert main._nemotron_avg_logprob(_FakeHyp()) == 0.0
    assert main._nemotron_avg_logprob(_FakeHyp(score=-3.0)) == 0.0
    assert main._nemotron_avg_logprob(_FakeHyp(y_sequence=[1, 2])) == 0.0


def test_avg_logprob_empty_sequence():
    assert main._nemotron_avg_logprob(_FakeHyp(score=-1.0, y_sequence=[])) == 0.0


def test_compression_ratio_repetitive_text_is_high():
    repetitive = "yes " * 50
    normal = "this is a perfectly ordinary sentence about transcription quality"
    assert main._text_compression_ratio(repetitive) > main._text_compression_ratio(normal)
    # Repetitive should clearly exceed the gate threshold (1.8).
    assert main._text_compression_ratio(repetitive) > main.COMPRESSION_RATIO_THRESHOLD


def test_compression_ratio_empty():
    assert main._text_compression_ratio("") == 0.0


def test_no_speech_prob_empty_text():
    assert main._nemotron_no_speech_prob("", 5.0) == 1.0
    assert main._nemotron_no_speech_prob("   ", 5.0) == 1.0


def test_no_speech_prob_tiny_text_on_long_audio():
    assert main._nemotron_no_speech_prob("a", 5.0) >= 0.6


def test_no_speech_prob_normal_text():
    assert main._nemotron_no_speech_prob("hello there how are you", 5.0) == 0.0


def test_phrase_repetition_detects_loop():
    text = "the meeting starts at noon " * 4
    assert main._has_phrase_repetition(text) is True


def test_phrase_repetition_passes_normal_text():
    text = "the meeting starts at noon and we will discuss the new release plan in detail"
    assert main._has_phrase_repetition(text) is False


def test_phrase_repetition_short_text_passes():
    assert main._has_phrase_repetition("yes yes yes") is False


def test_looks_like_hallucination_triggers_on_low_logprob():
    seg = {"avg_logprob": main.LOG_PROB_THRESHOLD - 0.1, "compression_ratio": 1.0}
    assert main._looks_like_hallucination([seg]) is True


def test_looks_like_hallucination_triggers_on_high_compression():
    seg = {"avg_logprob": 0.0, "compression_ratio": main.COMPRESSION_RATIO_THRESHOLD + 0.5}
    assert main._looks_like_hallucination([seg]) is True


def test_looks_like_hallucination_passes_clean_segment():
    seg = {"avg_logprob": -0.3, "compression_ratio": 1.2}
    assert main._looks_like_hallucination([seg]) is False
