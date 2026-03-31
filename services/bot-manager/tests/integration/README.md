# Integration Tests — bot-manager

## What this tests
- Bot lifecycle: create -> running -> stop -> cleaned up
- Redis pub/sub: bot status events published and received
- K8s pod spawning: bot pods created with correct env vars and resource limits
- Transcription connectivity: spawned bots can reach transcription-service
- Concurrent bot limit enforcement
- Bot cleanup on crash/timeout (no leaked pods)

## Dependencies
- bot-manager running
- Redis running
- K8s cluster accessible (or Docker for compose mode)
- transcription-service reachable

## How to invoke
Start a testing agent in this directory. It reads this README and the parent service README to understand what to verify.
