# Infrastructure Test Findings

**Date:** 2026-03-16T19:32Z
**Agent:** infra-testing

## Summary

| Component | Status | Detail |
|-----------|--------|--------|
| Redis | DEGRADED | 744 consumer lag on transcription_segments, 1 stuck pending message (36 days old) |
| PostgreSQL | PASS | Connected, alembic at head (a1b2c3d4e5f6), 139 MB, 6 connections |
| MinIO | DEGRADED | Accessible, bucket exists, but ~110 files in MinIO vs 2 rows in recordings table |

## Redis

### Connectivity
- PING: PONG
- Memory: 25.22 MB used, no maxmemory set (0 = unlimited), noeviction policy
- Total keys: 15
- Stream `transcription_segments`: 15,073 entries, 1 consumer group
- Stream `speaker_events_relative`: 19,698 entries, 1 consumer group

### DEGRADED: transcription_segments consumer lag = 744

Consumer group `collector_group` has read 14,329 of 15,073 entries. Lag of 744 messages. The collector is actively consuming (last ack seconds ago on recent messages), so the lag represents old entries from before the consumer group was created or after a reset — they were never delivered to the group.

**Root cause:** The stream has entries dating back to 2026-02-08 (entry `1770555700442-0`). The consumer group's `last-delivered-id` is `1773689274588-0` (2026-03-16). The 744 unread entries are likely scattered older entries that were added before the group was created or during a period when the collector was down. The collector only reads forward from `last-delivered-id`, so these 744 entries will never be consumed unless the group is reset.

### DEGRADED: 1 stuck pending message (36 days)

Entry `1770555700442-0` has been pending for 3,133,814+ seconds (~36 days) assigned to consumer `collector-main`. This is a session_start event from 2026-02-08 (meeting 349). It was delivered but never acknowledged. Not causing active harm but indicates the collector crashed or restarted without completing processing of this message.

**Action needed:** XCLAIM or XACK this entry to clear the pending list.

### No maxmemory configured

`maxmemory: 0` means Redis will grow unbounded. The two streams hold 34,771 entries total (~25 MB of data). Not urgent at current scale but a risk if streams aren't trimmed.

### speaker_events_relative: healthy

Lag = 16 (near-zero), 0 pending. Consumer group `collector_speaker_group` is keeping up.

### webhook_retry_queue: empty (0 items)

No failed webhooks pending retry. Clean.

## PostgreSQL

### Connectivity
- Connected as postgres superuser
- Database size: 139 MB
- Alembic version: `a1b2c3d4e5f6` (at head, current)
- Active connections: 6 total (4 idle, 1 idle in transaction, 1 active)

### Table sizes (disk)
| Table | Rows | Disk |
|-------|-----:|------|
| transcriptions | 417,563 | 113 MB |
| meetings | 8,542 | 10 MB |
| meeting_sessions | 16,556 | 4.6 MB |
| users | 1,593 | 1.0 MB |
| api_tokens | 1,708 | 496 KB |
| recordings | 2 | 160 KB |
| media_files | 2 | 64 KB |
| transcription_jobs | 0 | 88 KB |

Row counts match documented expectations. No anomalies.

### No issues found
- Schema is at head
- Connection count is healthy
- No long-running transactions detected

## Storage (MinIO)

### Connectivity
- MinIO alive, `vexa-recordings` bucket exists
- ~110 recording files present across multiple user directories
- Files range from 8 bytes to 110 MB, mix of .wav and .webm formats
- Date range: 2026-02-13 to 2026-03-15

### DEGRADED: Recording tracking gap (110 files in MinIO, 2 rows in Postgres)

The `recordings` table has 2 rows and `media_files` has 2 rows. MinIO has ~110 actual files across user directories (users 1, 2, 5, 7, 9, 23, 24, 37, 38, 39, 41, 45, 51, 54, 57, 58, 59, 83, 84, 1397, 1607, 1608, 1609, 1610, 1611, 1612, 1613).

**Root cause:** Recording upload code writes files to MinIO but the database tracking (recordings + media_files inserts) either fails silently, was added after the upload code, or the upload path bypasses the ORM tracking. The 2 tracked rows in Postgres are the original "recordings" feature from the doc (documented as "2 recordings in production"). The ~108 untracked files were likely added by a newer recording pipeline that writes directly to MinIO without creating database records.

**Impact:** No way to serve these recordings via the API (which queries Postgres), no lifecycle management, no cleanup possible without scanning MinIO directly. Orphaned storage.

## Risk Summary

| Risk | Severity | Action |
|------|----------|--------|
| transcription_segments lag 744 | Medium | Entries will never be consumed. XTRIM or accept data loss for old entries. |
| Stuck pending message (36 days) | Low | `XACK transcription_segments collector_group 1770555700442-0` to clear |
| No Redis maxmemory | Medium | Set `maxmemory` + eviction policy before streams grow unbounded |
| MinIO/Postgres tracking gap | High | ~108 recording files untracked in database. Fix recording pipeline to create DB records, or backfill. |
