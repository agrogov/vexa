# Bot Services Agent

## Scope
Bot internal services: audio capture, speaker identity, VAD, transcription client, segment publisher, recording, chat, screen content, hallucination filter, TTS.

## What you know
- audio.ts: per-speaker AudioContext pipelines — ScriptProcessorNode → resample → Float32 PCM. SpeakerStreamHandle per media element.
- speaker-identity.ts: track→speaker voting (LOCK_THRESHOLD=3, LOCK_RATIO=0.7). One-name-per-track, one-track-per-name enforced.
- speaker-streams.ts: confirmation buffer — accumulate audio, resubmit every interval, emit only when transcript beginning stabilizes. Hard cap force-flush.
- transcription-client.ts: HTTP POST to transcription-service with retries (default 3, 1s backoff).
- segment-publisher.ts: Redis XADD to transcription_segments stream + PUBLISH speaker events. Segments have segment_id = {session_uid}:{speakerId}:{seq}.
- vad.ts: Silero ONNX model via onnxruntime-node. Speech/silence binary filter.
- recording.ts: WAV file accumulation in /tmp, upload via HTTP. No retry on upload failure — silent loss.
- chat.ts: MutationObserver for chat messages, Redis storage. Can inject chat into transcription stream.
- hallucination-filter.ts: phrase files from hallucinations/*.txt + repetition detection. Multi-path resolution (dist/src/Docker).

## Critical questions
- Does recording upload have retry now? (known gap — silent loss on failure)
- Is VAD model file (silero_vad.onnx) present and loadable?
- Are hallucination phrase files found at runtime? (path resolution across dist/src/Docker)
- Does confirmation buffer actually advance? (or does it hit hard cap every time?)

## After every run
Update with buffer behavior observations, upload success rates, VAD load status.

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "no transcription" — report "no transcription because VAD model failed to load because silero_vad.onnx not found at expected path."
4. **Parallelize** — run independent checks concurrently. Don't wait for audio pipeline before checking Redis connectivity.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies: VAD model file (silero_vad.onnx), transcription-service (HTTP POST), Redis (segment publishing), hallucination phrase files. If segments are empty, trace: audio capture -> VAD -> transcription-client -> segment-publisher -> Redis.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
