"""Unit tests for the Nemotron quality-gate helpers.

These tests only exercise pure-Python helpers (no model load, no inference).
They import `main` lazily and skip if heavy ASR deps aren't installed in
the test environment.
"""
from __future__ import annotations

import pytest

main = pytest.importorskip("main")


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
