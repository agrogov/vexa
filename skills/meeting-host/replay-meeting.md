# Replay Meeting Skill

## What
Replay a real meeting transcript via TTS bots and validate transcription accuracy against the known source.

## Source data
`/home/dima/dev/vexa/test_data/meeting_saved_closed_caption.txt`

Format:
```
[Speaker Name] HH:MM:SS
text of what they said

[Another Speaker] HH:MM:SS
what they said
```

6 speakers, 693 lines. Real hackathon meeting.

## How to replay

1. Parse the transcript into utterances: `{speaker, timestamp, text}`
2. Map speakers to bot users (max 3 bots per meeting due to user limits):
   - Karl Moll → main user token
   - Francesco → Alice token
   - Others → Bob token (combined)
3. Launch bots with `bot_name` matching speaker names
4. For each utterance: `POST /bots/{platform}/{meeting}/speak` with the speaker's token
5. Gap between utterances: use real timestamps (or compress to 3s minimum)
6. One LISTENER bot (Carol token) transcribes everything

## Validation

Compare listener's CONFIRMED segments against the source transcript:
- For each source line, find the closest CONFIRMED segment by timestamp
- Word-by-word comparison
- Mark: ✅ exact, ⚠️ minor, ❌ major, 🚫 missing
- Calculate: % captured, % accurate

## Speed

Don't replay the full 693 lines. Pick a 2-minute window (30-40 utterances) with all speakers active. That's enough for validation.

## Parse script

```python
import re

def parse_transcript(path):
    utterances = []
    with open(path) as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = re.match(r'\[(.+?)\]\s+(\d+:\d+:\d+)', line)
        if match:
            speaker = match.group(1)
            timestamp = match.group(2)
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r'\[.+?\]\s+\d+:\d+:\d+', lines[i].strip()):
                text_lines.append(lines[i].strip())
                i += 1
            text = ' '.join(text_lines)
            if text:
                utterances.append({'speaker': speaker, 'timestamp': timestamp, 'text': text})
        else:
            i += 1
    return utterances
```
