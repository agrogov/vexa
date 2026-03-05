import json

from mapping.speaker_mapper import (
    STATUS_MAPPED,
    STATUS_MULTIPLE,
    STATUS_UNKNOWN,
    map_speaker_to_segment,
)


def _ev(event_type: str, ts: float, name: str | None, pid: str | None):
    payload = {
        "event_type": event_type,
        "participant_name": name,
        "participant_id_meet": pid,
    }
    return (json.dumps(payload), ts)


def test_flapping_short_bursts_are_ignored():
    events = [
        _ev("SPEAKER_START", 1000, "Test Speaker Alpha", "id-a"),
        _ev("SPEAKER_END", 1100, "Test Speaker Alpha", "id-a"),  # 100ms flap
        _ev("SPEAKER_START", 2000, "Test Speaker Alpha", "id-a"),
        _ev("SPEAKER_END", 2600, "Test Speaker Alpha", "id-a"),  # meaningful speech
    ]

    result = map_speaker_to_segment(2100, 2500, events)

    assert result["status"] == STATUS_MAPPED
    assert result["speaker_name"] == "Test Speaker Alpha"


def test_identity_is_stable_when_participant_id_rotates_for_same_name():
    events = [
        _ev("SPEAKER_START", 1000, "Test Speaker Beta", "id-1"),
        _ev("SPEAKER_END", 1600, "Test Speaker Beta", "id-1"),
        _ev("SPEAKER_START", 1700, "Test Speaker Beta", "id-2"),
        _ev("SPEAKER_END", 2400, "Test Speaker Beta", "id-2"),
    ]

    result = map_speaker_to_segment(1750, 2300, events)

    assert result["status"] == STATUS_MAPPED
    assert result["speaker_name"] == "Test Speaker Beta"
    assert result["participant_id_meet"] == "id-2"


def test_short_signal_loss_gap_is_merged_to_preserve_continuity():
    events = [
        _ev("SPEAKER_START", 1000, "Test Speaker Gamma", "a-1"),
        _ev("SPEAKER_END", 1600, "Test Speaker Gamma", "a-1"),
        _ev("SPEAKER_START", 2000, "Test Speaker Gamma", "a-2"),  # 400ms gap
        _ev("SPEAKER_END", 2700, "Test Speaker Gamma", "a-2"),
    ]

    # Segment is fully inside the short gap between END and next START.
    result = map_speaker_to_segment(1700, 1850, events)

    assert result["status"] == STATUS_MAPPED
    assert result["speaker_name"] == "Test Speaker Gamma"


def test_true_overlap_still_reported_as_multiple_when_ambiguous():
    events = [
        _ev("SPEAKER_START", 1000, "Test Speaker Delta", "id-delta"),
        _ev("SPEAKER_END", 2600, "Test Speaker Delta", "id-delta"),
        _ev("SPEAKER_START", 1200, "Test Speaker Epsilon", "id-epsilon"),
        _ev("SPEAKER_END", 2500, "Test Speaker Epsilon", "id-epsilon"),
    ]

    result = map_speaker_to_segment(1300, 2400, events)

    assert result["status"] == STATUS_MULTIPLE
    assert result["speaker_name"] in {"Test Speaker Delta", "Test Speaker Epsilon"}


def test_no_active_signal_gap_maps_to_single_dominant_nearby_speaker():
    events = [
        _ev("SPEAKER_START", 1000, "Test Speaker Zeta", "id-zeta"),
        _ev("SPEAKER_END", 3000, "Test Speaker Zeta", "id-zeta"),
        _ev("SPEAKER_START", 5000, "Test Speaker Zeta", "id-zeta-rotated"),
        _ev("SPEAKER_END", 7000, "Test Speaker Zeta", "id-zeta-rotated"),
    ]

    # Segment is in a true gap (not merged by SHORT_SILENCE_GAP_MS) but should map by context fallback.
    result = map_speaker_to_segment(3500, 4200, events)

    assert result["status"] == STATUS_MAPPED
    assert result["speaker_name"] == "Test Speaker Zeta"
    assert result["participant_id_meet"] == "id-zeta-rotated"


def test_no_active_signal_gap_stays_unknown_when_context_is_ambiguous():
    events = [
        _ev("SPEAKER_START", 1000, "Test Speaker Eta", "id-eta"),
        _ev("SPEAKER_END", 3000, "Test Speaker Eta", "id-eta"),
        _ev("SPEAKER_START", 1000, "Test Speaker Theta", "id-theta"),
        _ev("SPEAKER_END", 3000, "Test Speaker Theta", "id-theta"),
    ]

    result = map_speaker_to_segment(3500, 4200, events)

    assert result["status"] == STATUS_UNKNOWN
    assert result["speaker_name"] is None
