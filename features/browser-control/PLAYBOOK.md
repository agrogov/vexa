# Browser Control Playbook

Working admission flow for Google Meet. Learned through trial and error on 2026-03-17. Follow exactly — every detail matters.

## Google Meet: Create meeting + admit bot

### Step 1: Create meeting (5 seconds)

```bash
cd /home/dima/dev/playwright-vnc-poc && node -e "
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.connectOverCDP('http://localhost:9222');
  const p = b.contexts()[0].pages()[0] || await b.contexts()[0].newPage();
  await p.goto('https://meet.new', {waitUntil:'networkidle',timeout:30000});
  for (let i=0;i<15;i++) {
    const m = p.url().match(/meet\.google\.com\/([a-z]{3}-[a-z]{4}-[a-z]{3})/);
    if (m) { console.log('CODE:'+m[1]); break; }
    await p.waitForTimeout(1000);
  }
  try{await p.locator('button:has-text(\"Got it\")').click({timeout:2000})}catch{}
  await b.close();
})().catch(e=>console.error(e.message));
"
```

**What works:** `meet.new` auto-creates and auto-joins. Host is in the meeting immediately.
**What can go wrong:** URL stays at `/new` (rare). If so, wait longer or retry.
**CDP rule:** Open, do work, close. ONE connection at a time.

### Step 2: Launch bot (instant)

```bash
curl -s -X POST http://localhost:8056/bots \
  -H "X-API-Key: <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"<CODE>","voice_agent_enabled":true}'
```

**MUST use `voice_agent_enabled: true`** — gives bot PulseAudio for TTS. Without it, bot sends silence and SFU may not forward audio.

### Step 3: Wait 20-25 seconds

Bot needs time to: start container → launch Chrome → navigate to meeting → click "Ask to join" → reach lobby. This takes 20-25s consistently.

**Do NOT try to admit before 20s.** The bot won't be in lobby yet and you'll find no Admit button.

### Step 4: Admit from host (5 seconds)

```bash
cd /home/dima/dev/playwright-vnc-poc && node -e "
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.connectOverCDP('http://localhost:9222');
  const mp = b.contexts()[0].pages().find(p=>p.url().includes('meet.google.com'));
  if(!mp){console.log('NO_MEET_PAGE');await b.close();return}
  for(let i=0;i<20;i++){
    const r=await mp.evaluate(()=>{
      const a=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Admit'));
      if(a){a.click();return'ADMITTED'}
      return null;
    });
    if(r){console.log(r);break}
    console.log('wait...'+(i+1));
    await mp.waitForTimeout(3000);
  }
  const tiles=await mp.evaluate(()=>document.querySelectorAll('[data-participant-id]').length);
  console.log('TILES:'+tiles);
  await b.close();
})().catch(e=>console.error(e.message));
"
```

**Admit button selectors that work (2026-03-17):**
- `button` containing text "Admit" — catches "Admit", "Admit all", individual admit
- The "Admit one guest" chip in top-right corner also works but is harder to target
- "Admit all" in the dialog is the most reliable — one click admits everyone in lobby

**Verify from host:** `TILES >= 2` means bot is in the meeting (host + bot minimum).

### Step 5: Verify from bot side (5 seconds)

```bash
docker logs $(docker ps --filter name=vexa-bot -q | head -1) 2>&1 | grep -i "admitted\|ACTIVE\|media elements" | tail -5
```

**Expected:**
```
Bot admitted
ACTIVE status
Found 3 active media elements with audio tracks
```

**If bot says admitted but TILES is still 1:** false positive. Bot is NOT in the meeting. Wait longer and re-check host.

## Timing summary

```
T+0s:   Create meeting (CDP)
T+5s:   Meeting ready, launch bot (API)
T+25s:  Bot in lobby, admit (CDP)
T+30s:  Bot in meeting, verified
```

Total: ~30 seconds from start to verified bot in meeting.

## What we learned the hard way

1. **CDP connections are fragile.** Never hold a connection open. Script → connect → do work → disconnect.
2. **20s wait is mandatory.** Bot container startup + Chrome launch + navigation + Ask to join = 20s minimum.
3. **"Admit all" is most reliable.** Individual admit buttons are harder to find in the DOM.
4. **Verify from BOTH sides.** Bot logs say admitted + host People panel shows tiles >= 2.
5. **voice_agent_enabled: true is required** for bots that need to speak via TTS.
6. **Google Meet free accounts timeout.** Meetings last ~60 minutes but may show warnings earlier.
7. **meet.new auto-joins.** No need to click "Join now" — host is in immediately (usually).

## MS Teams: Create meeting + admit bot

### Step 1: Create meeting

Navigate to Teams Meet sidebar → "Create a meeting link" → join as organizer. See `features/realtime-transcription/ms-teams/.claude/commands/create-meeting.md` for full flow.

**Key difference from Google Meet:** No `teams.new` shortcut. Must navigate UI. Host must click "Join now" explicitly.

### Step 2-5: Same pattern

Launch bot with meeting URL (include `?p=` passcode), wait 20s, admit from lobby, verify.

**Teams admission selectors:** Look for "Admit" or "Let in" buttons in the People panel or lobby notification.

**Teams lobby:** Guests always go through lobby. Organizer must admit.
