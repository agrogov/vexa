import logging
from typing import List, Dict, Any, Optional, Tuple
import json
try:
    import redis.asyncio as aioredis
    import redis
except ModuleNotFoundError:  # pragma: no cover - enables lightweight local unit checks without redis package
    aioredis = Any  # type: ignore[assignment]

    class _RedisStub:
        class exceptions:
            class RedisError(Exception):
                pass

    redis = _RedisStub()  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Speaker mapping statuses
STATUS_UNKNOWN = "UNKNOWN"
STATUS_MAPPED = "MAPPED"
STATUS_MULTIPLE = "MULTIPLE_CONCURRENT_SPEAKERS"
STATUS_NO_SPEAKER_EVENTS = "NO_SPEAKER_EVENTS"
STATUS_ERROR = "ERROR_IN_MAPPING"

# Event fetch window constants
PRE_SEGMENT_SPEAKER_EVENT_FETCH_MS = 0
POST_SEGMENT_SPEAKER_EVENT_FETCH_MS = 500

# Mapping stability constants
MIN_SPEECH_BURST_MS = 350
SHORT_SILENCE_GAP_MS = 700
MIN_MEANINGFUL_OVERLAP_MS = 50
MULTIPLE_AMBIGUITY_RATIO = 1.2
FALLBACK_CONTEXT_WINDOW_MS = 15000
FALLBACK_DOMINANCE_RATIO = 2.0


def _normalize_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    normalized = " ".join(str(name).strip().split()).lower()
    return normalized or None


def _participant_key(event: Dict[str, Any], id_to_key: Dict[str, str]) -> Optional[str]:
    participant_id = event.get("participant_id_meet")
    normalized_name = _normalize_name(event.get("participant_name"))

    # Prefer name to survive ephemeral platform IDs.
    if normalized_name:
        key = f"name:{normalized_name}"
        if participant_id:
            id_to_key[participant_id] = key
        return key

    if participant_id:
        return id_to_key.get(participant_id) or f"id:{participant_id}"

    return None


def _choose_display_name(raw_name: Optional[str], normalized_name: str) -> str:
    if raw_name and str(raw_name).strip():
        return str(raw_name).strip()
    if normalized_name.startswith("name:"):
        return normalized_name[5:]
    return "unknown"


def _normalize_display_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    normalized = (
        str(name)
        .strip()
        .lower()
        .replace("\u00a0", " ")
    )
    normalized = " ".join(normalized.split())
    return normalized or None


def _build_speaker_intervals(
    parsed_events: List[Dict[str, Any]],
    interval_end_ms: float,
) -> Tuple[Dict[str, List[Tuple[float, float]]], Dict[str, Dict[str, Optional[str]]]]:
    intervals: Dict[str, List[Tuple[float, float]]] = {}
    states: Dict[str, Dict[str, Optional[float]]] = {}
    identity_meta: Dict[str, Dict[str, Optional[str]]] = {}
    id_to_key: Dict[str, str] = {}

    # Sort for deterministic state reconstruction.
    ordered_events = sorted(parsed_events, key=lambda ev: float(ev["relative_client_timestamp_ms"]))

    for event in ordered_events:
        event_type = event.get("event_type")
        if event_type not in {"SPEAKER_START", "SPEAKER_END"}:
            continue

        ts = float(event["relative_client_timestamp_ms"])
        key = _participant_key(event, id_to_key)
        if not key:
            logger.warning(f"[MapSpeaker] Event at {ts:.0f}ms missing both participant_id_meet and participant_name: {event}")
            continue

        meta = identity_meta.setdefault(key, {"name": None, "id": None})
        if event.get("participant_name"):
            meta["name"] = str(event.get("participant_name")).strip()
        if event.get("participant_id_meet"):
            # Keep most recent seen platform id for diagnostics/output.
            meta["id"] = str(event.get("participant_id_meet"))

        state = states.setdefault(key, {"active": False, "start": None})

        if event_type == "SPEAKER_START":
            # Duplicate START while already speaking -> noise.
            if state["active"]:
                continue
            state["active"] = True
            state["start"] = ts
            continue

        # SPEAKER_END
        if not state["active"]:
            # Stray END with no open START -> noise.
            continue

        start_ts = float(state["start"] or ts)
        end_ts = max(ts, start_ts)
        intervals.setdefault(key, []).append((start_ts, end_ts))
        state["active"] = False
        state["start"] = None

    for key, state in states.items():
        if state["active"] and state["start"] is not None:
            start_ts = float(state["start"])
            end_ts = max(interval_end_ms, start_ts)
            intervals.setdefault(key, []).append((start_ts, end_ts))

    # Debounce/hysteresis cleanup per participant.
    cleaned: Dict[str, List[Tuple[float, float]]] = {}
    for key, spans in intervals.items():
        if not spans:
            continue
        spans = sorted(spans, key=lambda span: span[0])

        # Remove tiny bursts (flapping START/END).
        filtered = [span for span in spans if (span[1] - span[0]) >= MIN_SPEECH_BURST_MS]
        if not filtered:
            continue

        merged: List[Tuple[float, float]] = [filtered[0]]
        for start_ts, end_ts in filtered[1:]:
            prev_start, prev_end = merged[-1]
            if start_ts - prev_end <= SHORT_SILENCE_GAP_MS:
                merged[-1] = (prev_start, max(prev_end, end_ts))
            else:
                merged.append((start_ts, end_ts))

        cleaned[key] = merged

    return cleaned, identity_meta


def map_speaker_to_segment(
    segment_start_ms: float,
    segment_end_ms: float,
    speaker_events_for_session: List[Tuple[str, float]],
    session_end_time_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """Map a speaker to a segment using stabilized participant identity and flap-resistant intervals."""
    active_speaker_name: Optional[str] = None
    active_participant_id: Optional[str] = None
    mapping_status = STATUS_UNKNOWN

    if not speaker_events_for_session:
        return {
            "speaker_name": None,
            "participant_id_meet": None,
            "status": STATUS_NO_SPEAKER_EVENTS,
        }

    parsed_events: List[Dict[str, Any]] = []
    for event_json, timestamp in speaker_events_for_session:
        try:
            event = json.loads(event_json)
            event["relative_client_timestamp_ms"] = float(timestamp)
            parsed_events.append(event)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse speaker event JSON: {event_json}")
            continue

    if not parsed_events:
        return {"speaker_name": None, "participant_id_meet": None, "status": STATUS_ERROR}

    interval_end_ms = session_end_time_ms or segment_end_ms
    intervals_by_participant, identity_meta = _build_speaker_intervals(parsed_events, interval_end_ms)

    logger.debug(
        f"[MapSpeaker] Segment: [{segment_start_ms:.0f}ms, {segment_end_ms:.0f}ms], "
        f"participants with cleaned intervals: {len(intervals_by_participant)}"
    )

    active_speakers_in_segment: List[Dict[str, Any]] = []
    for participant_key, intervals in intervals_by_participant.items():
        overlap_duration = 0.0
        for start_ts, end_ts in intervals:
            overlap_start = max(start_ts, segment_start_ms)
            overlap_end = min(end_ts, segment_end_ms)
            if overlap_start < overlap_end:
                overlap_duration += overlap_end - overlap_start

        if overlap_duration >= MIN_MEANINGFUL_OVERLAP_MS:
            meta = identity_meta.get(participant_key, {})
            display_name = _choose_display_name(meta.get("name"), participant_key)
            active_speakers_in_segment.append(
                {
                    "name": display_name,
                    "id": meta.get("id"),
                    "overlap_duration": overlap_duration,
                    "participant_key": participant_key,
                }
            )

    # Merge speakers that normalize to the same name to reduce false MULTIPLE cases from minor name churn.
    if active_speakers_in_segment:
        merged: Dict[str, Dict[str, Any]] = {}
        for speaker in active_speakers_in_segment:
            norm_name = _normalize_display_name(speaker["name"]) or speaker["name"]
            entry = merged.get(norm_name)
            if not entry:
                merged[norm_name] = dict(speaker)
            else:
                entry["overlap_duration"] += speaker["overlap_duration"]
                # Prefer existing id; keep first.
        active_speakers_in_segment = list(merged.values())

    if not active_speakers_in_segment:
        # Fallback: if a segment falls into a temporary signal gap, choose a dominant nearby speaker.
        context_start = max(0.0, segment_start_ms - FALLBACK_CONTEXT_WINDOW_MS)
        context_end = segment_end_ms + FALLBACK_CONTEXT_WINDOW_MS
        context_candidates: List[Dict[str, Any]] = []
        for participant_key, intervals in intervals_by_participant.items():
            context_overlap = 0.0
            for start_ts, end_ts in intervals:
                overlap_start = max(start_ts, context_start)
                overlap_end = min(end_ts, context_end)
                if overlap_start < overlap_end:
                    context_overlap += overlap_end - overlap_start
            if context_overlap >= MIN_SPEECH_BURST_MS:
                meta = identity_meta.get(participant_key, {})
                display_name = _choose_display_name(meta.get("name"), participant_key)
                context_candidates.append(
                    {
                        "name": display_name,
                        "id": meta.get("id"),
                        "context_overlap": context_overlap,
                    }
                )

        if context_candidates:
            context_candidates.sort(key=lambda x: x["context_overlap"], reverse=True)
            winner = context_candidates[0]
            if len(context_candidates) == 1:
                active_speaker_name = winner["name"]
                active_participant_id = winner["id"]
                mapping_status = STATUS_MAPPED
            else:
                second = context_candidates[1]
                ratio = winner["context_overlap"] / max(second["context_overlap"], 1.0)
                if ratio >= FALLBACK_DOMINANCE_RATIO:
                    active_speaker_name = winner["name"]
                    active_participant_id = winner["id"]
                    mapping_status = STATUS_MAPPED

            if mapping_status == STATUS_MAPPED:
                logger.info(
                    f"[MapSpeaker] Fallback MAPPED segment [{segment_start_ms:.0f}ms, {segment_end_ms:.0f}ms] "
                    f"to {active_speaker_name} (ID: {active_participant_id}, context={winner['context_overlap']:.0f}ms)"
                )
        if mapping_status != STATUS_MAPPED:
            logger.warning(
                f"[MapSpeaker] No active speakers found for segment [{segment_start_ms:.0f}ms, {segment_end_ms:.0f}ms]"
            )
            mapping_status = STATUS_UNKNOWN
    else:
        active_speakers_in_segment.sort(key=lambda x: x["overlap_duration"], reverse=True)
        winner = active_speakers_in_segment[0]
        active_speaker_name = winner["name"]
        active_participant_id = winner["id"]

        if len(active_speakers_in_segment) == 1:
            mapping_status = STATUS_MAPPED
        else:
            second = active_speakers_in_segment[1]
            ratio = winner["overlap_duration"] / max(second["overlap_duration"], 1.0)
            mapping_status = STATUS_MAPPED if ratio >= MULTIPLE_AMBIGUITY_RATIO else STATUS_MULTIPLE

        logger.info(
            f"[MapSpeaker] {mapping_status} segment [{segment_start_ms:.0f}ms, {segment_end_ms:.0f}ms] "
            f"to {active_speaker_name} (ID: {active_participant_id}, overlap={winner['overlap_duration']:.0f}ms)"
        )

    return {
        "speaker_name": active_speaker_name,
        "participant_id_meet": active_participant_id,
        "status": mapping_status,
    }


async def get_speaker_mapping_for_segment(
    redis_c: 'aioredis.Redis',
    session_uid: str,
    segment_start_ms: float,
    segment_end_ms: float,
    config_speaker_event_key_prefix: str,
    context_log_msg: str = "",
) -> Dict[str, Any]:
    """Fetch speaker events for a session from Redis and map a segment to a speaker."""
    if not session_uid:
        logger.warning(f"{context_log_msg} No session_uid provided. Cannot map speakers.")
        return {"speaker_name": None, "participant_id_meet": None, "status": STATUS_UNKNOWN}

    mapped_speaker_name: Optional[str] = None
    mapping_status: str = STATUS_UNKNOWN
    active_participant_id: Optional[str] = None

    try:
        speaker_event_key = f"{config_speaker_event_key_prefix}:{session_uid}"

        fetch_start_ms = PRE_SEGMENT_SPEAKER_EVENT_FETCH_MS
        fetch_end_ms = segment_end_ms + POST_SEGMENT_SPEAKER_EVENT_FETCH_MS

        logger.debug(f"{context_log_msg} Fetching speaker events from Redis: [{fetch_start_ms:.0f}ms, {fetch_end_ms:.0f}ms]")

        speaker_events_raw = await redis_c.zrangebyscore(
            speaker_event_key,
            min=fetch_start_ms,
            max=fetch_end_ms,
            withscores=True,
        )

        try:
            late_min = fetch_end_ms
            late_max = segment_end_ms + 3000
            if late_max > late_min:
                late_events_raw = await redis_c.zrangebyscore(
                    speaker_event_key,
                    min=late_min,
                    max=late_max,
                    withscores=False,
                )
                if late_events_raw:
                    counts: Dict[str, int] = {}
                    ids: set[str] = set()
                    for ev in late_events_raw[:50]:
                        try:
                            ev_str = ev.decode("utf-8") if isinstance(ev, (bytes, bytearray)) else str(ev)
                            obj = json.loads(ev_str)
                            event_type = str(obj.get("event_type") or "unknown")
                            counts[event_type] = counts.get(event_type, 0) + 1
                            pid = obj.get("participant_id_meet") or obj.get("participant_name") or ""
                            pid = str(pid)
                            if pid:
                                ids.add(pid[:8])
                        except Exception:
                            counts["unparseable"] = counts.get("unparseable", 0) + 1
                    logger.info(
                        f"{context_log_msg} [DiagLateEvents] UID:{session_uid[:8]} "
                        f"segEnd={segment_end_ms:.0f}ms bufferEnd={fetch_end_ms:.0f}ms lateCount={len(late_events_raw)} "
                        f"types={counts} participantIdPrefixes={sorted(list(ids))[:5]}"
                    )
        except Exception as diag_err:
            logger.debug(f"{context_log_msg} [DiagLateEvents] failed: {diag_err}")

        speaker_events_for_mapper: List[Tuple[str, float]] = []
        for event_data, score_ms in speaker_events_raw:
            if isinstance(event_data, bytes):
                event_json_str = event_data.decode("utf-8")
            elif isinstance(event_data, str):
                event_json_str = event_data
            else:
                logger.warning(
                    f"{context_log_msg} UID:{session_uid} Seg:{segment_start_ms}-{segment_end_ms} "
                    f"Unexpected speaker event data type from Redis: {type(event_data)}. Skipping this event."
                )
                continue
            speaker_events_for_mapper.append((event_json_str, float(score_ms)))

        log_prefix_detail = f"{context_log_msg} UID:{session_uid} Seg:{segment_start_ms:.0f}-{segment_end_ms:.0f}ms"

        if not speaker_events_for_mapper:
            logger.debug(f"{log_prefix_detail} No speaker events in Redis for mapping.")
            mapping_status = STATUS_NO_SPEAKER_EVENTS
        else:
            logger.debug(f"{log_prefix_detail} {len(speaker_events_for_mapper)} speaker events for mapping.")

        mapping_result = map_speaker_to_segment(
            segment_start_ms=segment_start_ms,
            segment_end_ms=segment_end_ms,
            speaker_events_for_session=speaker_events_for_mapper,
            session_end_time_ms=None,
        )

        mapped_speaker_name = mapping_result.get("speaker_name")
        active_participant_id = mapping_result.get("participant_id_meet")
        mapping_status = mapping_result.get("status", STATUS_ERROR)

        if mapping_status != STATUS_NO_SPEAKER_EVENTS:
            logger.info(f"{log_prefix_detail} Result: Name='{mapped_speaker_name}', Status='{mapping_status}'")

    except redis.exceptions.RedisError as redis_err:
        logger.error(
            f"{context_log_msg} UID:{session_uid} Seg:{segment_start_ms}-{segment_end_ms} "
            f"Redis error fetching/processing speaker events: {redis_err}",
            exc_info=True,
        )
        mapping_status = STATUS_ERROR
    except Exception as map_err:
        logger.error(
            f"{context_log_msg} UID:{session_uid} Seg:{segment_start_ms}-{segment_end_ms} Speaker mapping error: {map_err}",
            exc_info=True,
        )
        mapping_status = STATUS_ERROR

    return {
        "speaker_name": mapped_speaker_name,
        "participant_id_meet": active_participant_id,
        "status": mapping_status,
    }
