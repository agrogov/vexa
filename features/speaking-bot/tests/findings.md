# Speaking Bot Test Findings

## Confidence Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Speak endpoint accepts command | 0 | Not tested | — | POST speak command, verify 200 response |
| TTS generates audio | 0 | Not tested | — | Check tts-service logs for audio generation |
| Bot plays audio | 0 | Not tested | — | Verify PulseAudio virtual mic receives output |
| Meeting participants hear bot | 0 | Not tested | — | End-to-end: speak command → audible in meeting |
| Command queuing | 0 | Not tested | — | Send multiple speak commands, verify sequential playback |
