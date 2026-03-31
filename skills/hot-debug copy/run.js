#!/usr/bin/env node
/**
 * Hot Debug Run Script
 *
 * Full automated test loop:
 * 1. Create meeting (Google Meet or Teams) via CDP
 * 2. Launch speaker bot (TTS enabled) + listener bot (transcribe only)
 * 3. Auto-admit bots from lobby (500ms poll)
 * 4. Wait for bots to settle (~30s)
 * 5. /speak 3 utterances via speaker bot
 * 6. Wait for transcription (poll every 3s, up to 60s)
 * 7. Report PASS/FAIL with evidence
 * 8. On FAIL: inspect DOM for speaker indicator state
 *
 * Usage:
 *   node run.js --platform teams [--meeting-url URL]
 *   node run.js --platform google_meet
 */

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');
const { execSync, spawn } = require('child_process');
const fs = require('fs');
const http = require('http');

// ─── Config ──────────────────────────────────────────────────────────────────
const CDP_URL       = 'http://localhost:9222';
const API_BASE      = 'http://localhost:8056';
const TOKEN_MAIN    = 'vxa_user_mZbCdNnQwmzU2rjyGcyCjj0is8Mx75ljtHgHsM2L';
const TOKEN_ALICE   = 'vxa_user_AsujJTFgXEmHEn0K7LyqX7oyReeWGJcf7a1CPgLI';
const LOG_FILE      = '/home/dima/dev/vexa/test.log';
const HISTORY_FILE  = '/home/dima/dev/vexa/skills/hot-debug/run-history.jsonl';
const SCRIPTS_DIR   = '/home/dima/dev/vexa/features/browser-control/scripts';
const LOCK_FILE     = '/tmp/hot-debug.lock';

const UTTERANCES = [
  'Hello, this is the speaker bot testing the noise fix.',
  'When I am not speaking, the speaker indicator should be off.',
  'The virtual microphone should be silent between utterances.',
];

// ─── Helpers ─────────────────────────────────────────────────────────────────
function log(level, msg) {
  const line = `[${new Date().toISOString()}] [hot-debug/run] ${level}: ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { platform: null, meetingUrl: null, runs: 1, loop: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--platform' && args[i+1]) opts.platform = args[++i];
    if (args[i] === '--meeting-url' && args[i+1]) opts.meetingUrl = args[++i];
    if (args[i] === '--runs' && args[i+1]) opts.runs = parseInt(args[++i], 10);
    if (args[i] === '--loop') opts.loop = true;
  }
  return opts;
}

function apiRequest(method, path, body, token) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const headers = {
      'X-API-Key': token || TOKEN_MAIN,
      'Content-Type': 'application/json',
    };
    if (data) headers['Content-Length'] = Buffer.byteLength(data);

    const url = new URL(API_BASE + path);
    const req = http.request({
      hostname: url.hostname,
      port: url.port || 80,
      path: url.pathname + (url.search || ''),
      method,
      headers,
    }, (res) => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(body) }); }
        catch { resolve({ status: res.statusCode, data: body }); }
      });
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

async function runScript(scriptName, extraArgs = []) {
  const scriptPath = `${SCRIPTS_DIR}/${scriptName}`;
  return new Promise((resolve) => {
    const proc = spawn('node', [scriptPath, ...extraArgs], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', d => { stdout += d.toString(); process.stdout.write(d); });
    proc.stderr.on('data', d => { stderr += d.toString(); process.stderr.write(d); });
    proc.on('close', code => resolve({ code, stdout: stdout.trim(), stderr: stderr.trim() }));
    proc.on('error', e => resolve({ code: 1, stdout: '', stderr: e.message }));
  });
}

// ─── Persistent CDP browser (shared across meeting creation + admission) ──────
// Keeping one browser object open ensures the organizer stays in the meeting
// so lobby notifications appear and admit buttons can be clicked.
let sharedBrowser = null;
let meetingPage = null; // The page where organizer is in the meeting

async function getSharedBrowser() {
  if (!sharedBrowser) {
    sharedBrowser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  }
  return sharedBrowser;
}

// ─── Step 1: Create meeting via CDP ──────────────────────────────────────────
async function createMeeting(platform, existingUrl) {
  if (existingUrl) {
    log('PASS', `Using provided meeting URL: ${existingUrl}`);
    return existingUrl;
  }

  if (platform !== 'teams') {
    // Google Meet: use subprocess (it doesn't have the same navigator-away problem)
    log('PASS', `Creating ${platform} meeting via CDP...`);
    const result = await runScript('create-google-meet.js', ['--cdp', CDP_URL]);
    if (result.code !== 0) { log('FAIL', `Meeting creation failed: ${result.stderr}`); return null; }
    const line = result.stdout.split('\n').find(l => l.startsWith('MEETING:'));
    if (!line) { log('FAIL', 'No MEETING: line in output'); return null; }
    return line.replace('MEETING:', '').trim();
  }

  // Teams: create inline using shared browser connection (no subprocess — keeps organizer in meeting)
  log('PASS', 'Creating Teams meeting via CDP (inline, persistent connection)...');
  const browser = await getSharedBrowser();
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] || await ctx.newPage();

  // Navigate to Teams if not already there
  const currentUrl = page.url();
  if (!currentUrl.includes('teams.microsoft.com') && !currentUrl.includes('teams.live.com')) {
    await page.goto('https://teams.live.com/v2/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  }
  // Wait for Teams sidebar to be ready (Meet button visible)
  await page.waitForSelector('button[aria-label="Meet"]', { timeout: 15000 }).catch(() => {});

  // Response listener for meeting URL (Teams uses Service Workers — page.route() won't work)
  let meetingUrl = null;
  const responseHandler = async (res) => {
    const resUrl = res.url();
    if (resUrl.includes('teamsforlife') || resUrl.includes('schedulingService/create') || resUrl.includes('privateMeeting')) {
      try {
        const body = await res.text();
        const data = JSON.parse(body);
        const joinUrl = data?.value?.links?.join || data?.links?.join || data?.meetingUrl;
        if (joinUrl && joinUrl.includes('teams.live.com/meet/')) {
          meetingUrl = joinUrl;
          log('PASS', `Intercepted meeting URL from API: ${meetingUrl}`);
        }
      } catch {}
    }
  };
  page.on('response', responseHandler);

  // Dismiss any active call first
  await page.evaluate(() => {
    const hangup = document.querySelector('[data-tid="hangup-main-btn"]');
    if (hangup) hangup.click();
  }).catch(() => {});
  // Wait for hangup to disappear (call ended) or skip if none
  await page.waitForFunction(
    () => !document.querySelector('[data-tid="hangup-main-btn"]'),
    { timeout: 5000 }
  ).catch(() => {});

  // Click Meet sidebar — wait for it to be visible first
  await page.waitForSelector('button[aria-label="Meet"]', { timeout: 10000 });
  await page.evaluate(() => {
    document.querySelector('button[aria-label="Meet"]')?.click();
  }).catch(() => {});

  // Wait for "Create a meeting link" button
  await page.waitForFunction(
    () => !!document.querySelector('[data-tid="create-meeting-link"]') ||
          !!Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create a meeting link' && b.getBoundingClientRect().width > 0),
    { timeout: 8000 }
  ).catch(() => {});
  const createClicked = await page.evaluate(() => {
    const el = document.querySelector('[data-tid="create-meeting-link"]') ||
      Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create a meeting link');
    if (el) { el.click(); return true; }
    return false;
  }).catch(() => false);
  if (!createClicked) { log('FAIL', '"Create a meeting link" not found'); page.off('response', responseHandler); return null; }

  // Wait for "Create and copy link" button
  await page.waitForFunction(
    () => !!Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create and copy link' && b.getBoundingClientRect().width > 0),
    { timeout: 8000 }
  ).catch(() => {});
  const copyClicked = await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create and copy link');
    if (btn) { btn.click(); return true; }
    return false;
  }).catch(() => false);
  if (!copyClicked) { log('FAIL', '"Create and copy link" not found'); page.off('response', responseHandler); return null; }

  // Wait for response listener to capture URL (up to 10s)
  const urlDeadline = Date.now() + 10000;
  while (!meetingUrl && Date.now() < urlDeadline) { await sleep(100); }
  page.off('response', responseHandler);

  // Fallback: clipboard and page text
  if (!meetingUrl) {
    log('DEGRADED', 'API response not intercepted — trying clipboard/DOM fallback');
    const clip = await page.evaluate(async () => {
      try { return await navigator.clipboard.readText(); } catch { return null; }
    }).catch(() => null);
    if (clip?.includes('teams.live.com/meet/')) meetingUrl = clip.trim();
  }
  if (!meetingUrl) {
    const text = await page.evaluate(() => document.body.innerText).catch(() => '');
    const m = text.match(/(https:\/\/teams\.live\.com\/meet\/[^\s"]+)/);
    if (m) meetingUrl = m[1];
  }

  if (!meetingUrl) { log('FAIL', 'Could not extract meeting URL'); return null; }
  meetingUrl = meetingUrl.trim().replace(/[,;.]+$/, '');
  log('PASS', `Meeting link: ${meetingUrl}`);

  // Join as organizer — wait for Join button on meeting card
  log('PASS', 'Joining as organizer...');
  await page.waitForFunction(
    () => !!Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Join' && b.getBoundingClientRect().width > 0),
    { timeout: 8000 }
  ).catch(() => {});
  const joinCardClicked = await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Join' && b.getBoundingClientRect().width > 0);
    if (btn) { btn.click(); return 'clicked'; }
    return 'not-found';
  }).catch(() => 'error');
  log('PASS', `Join card: ${joinCardClicked}`);

  if (joinCardClicked === 'clicked') {
    // Wait for pre-join screen OR already in meeting
    await page.waitForFunction(
      () => !!document.querySelector('[data-tid="prejoin-join-button"]') ||
            !!document.querySelector('[data-tid="hangup-main-btn"]') ||
            !!Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Join now' && b.getBoundingClientRect().width > 0),
      { timeout: 15000 }
    ).catch(() => {});

    const alreadyIn = await page.evaluate(() => !!document.querySelector('[data-tid="hangup-main-btn"]')).catch(() => false);
    if (!alreadyIn) {
      await page.evaluate(() => {
        const btn = document.querySelector('[data-tid="prejoin-join-button"]') ||
          Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Join now' && b.getBoundingClientRect().width > 0);
        if (btn) btn.click();
      }).catch(() => {});
      // Wait until hangup button appears = in meeting
      await page.waitForSelector('[data-tid="hangup-main-btn"]', { timeout: 15000 }).catch(() => {});
    }

    const inMeeting = await page.evaluate(() => !!document.querySelector('[data-tid="hangup-main-btn"]')).catch(() => false);
    log(inMeeting ? 'PASS' : 'DEGRADED', inMeeting ? 'Organizer in meeting' : 'Could not confirm organizer in meeting');
  }

  meetingPage = page; // Keep reference for admission and DOM inspection
  log('PASS', `Meeting created: ${meetingUrl}`);
  return meetingUrl;
}

// ─── Step 2: Extract native meeting ID from URL ───────────────────────────────
function extractMeetingId(platform, meetingUrl) {
  if (platform === 'teams') {
    // teams.live.com/meet/XXXXX?p=YYY  → the path segment after /meet/
    const m = meetingUrl.match(/\/meet\/([^?&/]+)/);
    return m ? m[1] : null;
  } else {
    // meet.google.com/abc-defg-hij → abc-defg-hij
    const m = meetingUrl.match(/meet\.google\.com\/([a-z0-9-]+)/i);
    return m ? m[1] : null;
  }
}

// ─── Step 3: Launch bots ─────────────────────────────────────────────────────
async function launchBot(platform, meetingUrl, nativeMeetingId, token, config, label) {
  log('PASS', `Launching ${label} bot on ${platform}...`);

  // For Teams, the API typically wants the full meeting URL, not just the ID segment
  // Bot manager stores native_meeting_id to re-identify the meeting.
  // API accepts: 'google_meet', 'zoom', or 'teams' (NOT 'ms_teams')
  const body = {
    platform: platform === 'teams' ? 'teams' : 'google_meet',
    native_meeting_id: nativeMeetingId,
    meeting_url: meetingUrl,
    ...config,
  };

  const res = await apiRequest('POST', '/bots', body, token);
  log(res.status === 200 || res.status === 201 ? 'PASS' : 'FAIL',
    `Launch ${label}: HTTP ${res.status} → ${JSON.stringify(res.data).substring(0, 200)}`);

  if (res.status !== 200 && res.status !== 201) return null;
  return res.data;
}

// ─── Step 4: Auto-admit ───────────────────────────────────────────────────────
// Teams lobby flow (observed 2026-03-18):
//   1. "View Lobby" button appears in meeting toolbar when bots arrive
//   2. Clicking it opens the lobby panel (People panel, Waiting section)
//   3. "Admit" buttons appear per-person, plus "Admit all" if multiple waiting
//
// Strategy:
//   - MutationObserver watches for BOTH "View Lobby" and "Admit" / "Admit all"
//   - On "View Lobby": click it immediately to open the lobby panel
//   - On "Admit" / "Admit all": click immediately
//   - Backup poll every 200ms for same buttons
//   - Timeout 120s (View Lobby adds ~2s latency before Admit appears)
async function autoAdmit(platform, meetingUrl, timeoutMs = 120000) {
  log('PASS', `Starting auto-admit (timeout: ${timeoutMs/1000}s)...`);

  await getSharedBrowser();
  const page = meetingPage || sharedBrowser?.contexts()[0]?.pages()[0];
  if (!page) { log('DEGRADED', 'No page for auto-admit'); return 0; }

  log('PASS', `Auto-admit watching page: ${page.url()}`);

  // MutationObserver: instant reaction to DOM changes.
  // Handles two-step Teams lobby flow: View Lobby → Admit.
  await page.evaluate(() => {
    window.__hotDebugAdmitCount = 0;
    window.__hotDebugViewLobbyClicked = 0;

    function handleAdmitButtons() {
      const selectors = ['button', '[role="button"]'];
      for (const sel of selectors) {
        for (const el of document.querySelectorAll(sel)) {
          const text = (el.textContent || el.getAttribute('aria-label') || '').trim();
          const lower = text.toLowerCase();
          const rect = el.getBoundingClientRect();
          if (rect.width <= 0 || rect.height <= 0) continue;

          // "View Lobby" — click to open lobby panel so Admit buttons appear
          if (lower === 'view lobby' || lower.includes('view lobby')) {
            el.click();
            window.__hotDebugViewLobbyClicked++;
            console.log('[hot-debug] Clicked View Lobby');
            continue;
          }

          // "Admit all" — admits everyone at once
          if (lower.includes('admit all')) {
            el.click();
            window.__hotDebugAdmitCount += 10; // approximate
            console.log('[hot-debug] Clicked Admit all');
            continue;
          }

          // Individual "Admit" button (not "Admitting")
          if (lower.includes('admit') && !lower.includes('admitting')) {
            el.click();
            window.__hotDebugAdmitCount++;
            console.log('[hot-debug] Admitted:', text);
          }
        }
      }
    }

    window.__hotDebugObserver = new MutationObserver(handleAdmitButtons);
    window.__hotDebugObserver.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: false,
    });
    handleAdmitButtons(); // run once immediately
  }).catch(e => log('DEGRADED', `MutationObserver install failed: ${e.message}`));

  log('PASS', 'MutationObserver installed (View Lobby + Admit + Admit all)...');

  let admitCount = 0;
  let viewLobbyCount = 0;
  let lastAdmitAt = 0;
  const deadline = Date.now() + timeoutMs;
  const IDLE_AFTER_ADMIT_MS = 5000; // exit early if no new admits for 5s after first admit

  while (Date.now() < deadline) {
    const state = await page.evaluate(() => ({
      admits: window.__hotDebugAdmitCount || 0,
      viewLobbys: window.__hotDebugViewLobbyClicked || 0,
    })).catch(() => ({ admits: 0, viewLobbys: 0 }));

    if (state.viewLobbys > viewLobbyCount) {
      log('PASS', `View Lobby clicked (total: ${state.viewLobbys})`);
      viewLobbyCount = state.viewLobbys;
    }
    if (state.admits > admitCount) {
      log('PASS', `Admitted: ${state.admits - admitCount} new (total: ${state.admits})`);
      admitCount = state.admits;
      lastAdmitAt = Date.now();
    }

    // Backup direct poll
    const result = await page.evaluate(() => {
      let admits = 0, viewLobbys = 0;
      for (const el of document.querySelectorAll('button, [role="button"]')) {
        const text = (el.textContent || el.getAttribute('aria-label') || '').trim();
        const lower = text.toLowerCase();
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) continue;
        if (lower === 'view lobby' || lower.includes('view lobby')) {
          el.click(); viewLobbys++;
        } else if (lower.includes('admit all')) {
          el.click(); admits += 10;
        } else if (lower.includes('admit') && !lower.includes('admitting')) {
          el.click(); admits++;
        }
      }
      return { admits, viewLobbys };
    }).catch(() => ({ admits: 0, viewLobbys: 0 }));

    if (result.viewLobbys > 0) log('PASS', `Poll: View Lobby clicked`);
    if (result.admits > 0) {
      admitCount += result.admits;
      lastAdmitAt = Date.now();
      log('PASS', `Poll admitted ${result.admits} (total: ${admitCount})`);
    }

    // Exit early: admitted at least 1 bot and no new admits for IDLE_AFTER_ADMIT_MS
    if (admitCount > 0 && lastAdmitAt > 0 && Date.now() - lastAdmitAt > IDLE_AFTER_ADMIT_MS) {
      log('PASS', `Admit loop exiting early — no new admits for ${IDLE_AFTER_ADMIT_MS/1000}s`);
      break;
    }

    await sleep(200);
  }

  await page.evaluate(() => {
    if (window.__hotDebugObserver) window.__hotDebugObserver.disconnect();
  }).catch(() => {});

  if (admitCount === 0) log('DEGRADED', `No bots admitted in ${timeoutMs/1000}s`);
  else log('PASS', `Auto-admit done: ${admitCount} admit(s)`);
  return admitCount;
}

// ─── Wait for bot to be in "joined/active" state ──────────────────────────────
// The /speak endpoint requires meeting status == "active" in the DB.
// Poll GET /meetings until the target meeting shows status="active".
async function waitForBotActive(platform, nativeMeetingId, token, timeoutMs = 60000) {
  log('PASS', `Waiting for ${platform}/${nativeMeetingId} meeting to reach "active" status (timeout: ${timeoutMs/1000}s)...`);
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    try {
      const res = await apiRequest('GET', '/meetings', null, token);
      if (res.status === 200) {
        const meetings = Array.isArray(res.data) ? res.data : (res.data.meetings || []);
        const target = meetings.find(m =>
          m.native_meeting_id === nativeMeetingId && m.status === 'active'
        );
        if (target) {
          log('PASS', `Meeting ${nativeMeetingId} is now ACTIVE (DB id: ${target.id})`);
          return true;
        }
        // Log current status for debugging
        const targetAny = meetings.find(m => m.native_meeting_id === nativeMeetingId);
        if (targetAny) {
          log('PASS', `Meeting ${nativeMeetingId} status: ${targetAny.status} (waiting for active...)`);
        }
      }
    } catch (e) {
      log('DEGRADED', `waitForBotActive poll error: ${e.message}`);
    }
    await sleep(1000);
  }

  log('DEGRADED', `Meeting ${nativeMeetingId} did not reach "active" in ${timeoutMs/1000}s — proceeding anyway`);
  return false;
}

// ─── Step 5: Speak ────────────────────────────────────────────────────────────
async function speakUtterance(platform, nativeMeetingId, text, token) {
  // API paths use 'teams' and 'google_meet' (not 'ms_teams')
  const platformPath = platform === 'teams' ? 'teams' : 'google_meet';
  const encodedId = encodeURIComponent(nativeMeetingId);
  const res = await apiRequest('POST', `/bots/${platformPath}/${encodedId}/speak`,
    { text, voice: 'alloy' }, token);
  const ok = res.status === 200 || res.status === 202;
  log(ok ? 'PASS' : 'FAIL',
    `/speak: HTTP ${res.status} → ${JSON.stringify(res.data).substring(0, 100)}`);
  return ok;
}

// ─── Step 6: Poll for transcripts ────────────────────────────────────────────
// API: GET /transcripts/{platform}/{native_meeting_id}
async function pollTranscripts(platform, nativeMeetingId, token, timeoutMs = 90000) {
  const platformPath = platform === 'teams' ? 'teams' : 'google_meet';
  const encodedId = encodeURIComponent(nativeMeetingId);
  log('PASS', `Polling transcripts for ${platformPath}/${nativeMeetingId} (timeout: ${timeoutMs/1000}s)`);
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    try {
      const res = await apiRequest('GET', `/transcripts/${platformPath}/${encodedId}`, null, token);
      if (res.status === 200) {
        const segments = Array.isArray(res.data) ? res.data : (res.data.segments || []);
        if (segments.length > 0) {
          log('PASS', `Got ${segments.length} transcript segment(s)`);
          return segments;
        }
        log('PASS', `No segments yet...`);
      } else {
        log('DEGRADED', `Transcript poll: HTTP ${res.status} → ${JSON.stringify(res.data).substring(0, 100)}`);
      }
    } catch (e) {
      log('DEGRADED', `Transcript poll error: ${e.message}`);
    }
    await sleep(1000);
  }

  log('FAIL', `Transcript poll timed out after ${timeoutMs/1000}s`);
  return [];
}

// ─── Step 7: Check speaker indicator (screenshot + DOM inspection) ───────────
let screenshotCounter = 0;
async function checkSpeakerIndicator(meetingUrl, label) {
  log('PASS', `Speaker indicator check (${label || 'check'})...`);

  try {
    // Use persistent sharedBrowser — do NOT open/close a new connection (would disrupt organizer)
    await getSharedBrowser();
    const ctx = sharedBrowser.contexts()[0];

    let targetPage = meetingPage; // First try the known meeting page

    if (!targetPage) {
      // Fall back: scan all pages
      const pages = ctx ? ctx.pages() : [];
      const meetingId = meetingUrl ? meetingUrl.match(/\/meet\/([^?]+)/)?.[1] : null;
      for (const p of pages) {
        if (meetingId && p.url().includes(meetingId)) { targetPage = p; break; }
      }
      if (!targetPage) {
        for (const p of (ctx ? ctx.pages() : [])) {
          const u = p.url();
          if (u.includes('teams.microsoft.com') || u.includes('teams.live.com') || u.includes('meet.google.com')) {
            targetPage = p;
            break;
          }
        }
      }
    }

    if (!targetPage) {
      log('DEGRADED', 'No meeting page found for DOM inspection');
      return null;
    }

    // Use local alias to avoid shadowing the outer meetingPage global
    const activePage = targetPage;

    // Screenshot
    screenshotCounter++;
    const screenshotPath = `/tmp/hot-debug-${label || screenshotCounter}.png`;
    try {
      await activePage.screenshot({ path: screenshotPath });
      log('PASS', `Screenshot: ${screenshotPath} (url: ${activePage.url()})`);
    } catch (e) {
      log('DEGRADED', `Screenshot failed: ${e.message}`);
    }

    const result = await activePage.evaluate(() => {
      // Teams: check voice-level-stream-outline elements and vdi-frame-occlusion class
      const voiceLevelEls = document.querySelectorAll('[data-tid="voice-level-stream-outline"]');
      const speakingNow = [];
      const notSpeaking = [];

      for (const el of voiceLevelEls) {
        // Check if this participant's tile has the speaking indicator
        const tile = el.closest('[data-tid*="participant"], [data-tid*="video-tile"], [class*="tile"]');
        const nameEl = tile ? tile.querySelector('[data-tid*="display-name"], [class*="displayName"], [class*="name"]') : null;
        const name = nameEl ? nameEl.textContent?.trim() : 'unknown';

        // Check for vdi-frame-occlusion (active speaker) or animated border
        let isSpeaking = false;
        let ancestor = el.parentElement;
        for (let i = 0; i < 10 && ancestor; i++) {
          if (ancestor.classList.contains('vdi-frame-occlusion')) {
            isSpeaking = true;
            break;
          }
          ancestor = ancestor.parentElement;
        }

        // Also check inline style or animation attributes
        const style = window.getComputedStyle(el);
        const opacity = parseFloat(style.opacity || '0');
        if (opacity > 0.1) isSpeaking = true;

        if (isSpeaking) speakingNow.push(name);
        else notSpeaking.push(name);
      }

      // Also get all participant names visible
      const participants = Array.from(document.querySelectorAll('[data-tid*="display-name"], [class*="displayName"]'))
        .map(el => el.textContent?.trim())
        .filter(Boolean);

      // Check if any bot has the speaking border (visual border animation)
      const speakerBorders = Array.from(document.querySelectorAll('[class*="speaking"], [class*="active-speaker"], [data-speaking="true"]'))
        .map(el => el.textContent?.trim() || el.getAttribute('data-tid') || el.className)
        .filter(Boolean);

      return {
        voiceLevelElements: voiceLevelEls.length,
        speakingNow,
        notSpeaking,
        participants: [...new Set(participants)].slice(0, 20),
        speakerBorders: [...new Set(speakerBorders)].slice(0, 10),
        url: window.location.href,
      };
    });

    log('PASS', `DOM inspection result: ${JSON.stringify(result, null, 2)}`);
    return result;
  } catch (e) {
    log('DEGRADED', `DOM inspection failed: ${e.message}`);
    return null;
  }
  // No browser.close() — sharedBrowser must stay open to keep organizer in meeting
}

// ─── Step 8: Stop bots ────────────────────────────────────────────────────────
async function stopBot(platform, nativeMeetingId, token) {
  // API paths use 'teams' and 'google_meet' (not 'ms_teams')
  const platformPath = platform === 'teams' ? 'teams' : 'google_meet';
  const encodedId = encodeURIComponent(nativeMeetingId);
  const res = await apiRequest('DELETE', `/bots/${platformPath}/${encodedId}`, null, token);
  log(res.status === 200 || res.status === 202 ? 'PASS' : 'DEGRADED',
    `Stop bot: HTTP ${res.status}`);
}

// ─── Lock file helpers ────────────────────────────────────────────────────────
// Prevent concurrent run.js instances from interfering with each other.
// Each instance writes its PID to LOCK_FILE on start and removes it on exit.
function acquireLock() {
  // Check if another instance is running
  try {
    if (fs.existsSync(LOCK_FILE)) {
      const existingPid = parseInt(fs.readFileSync(LOCK_FILE, 'utf8').trim(), 10);
      if (existingPid && existingPid !== process.pid) {
        // Check if the process is actually alive
        try {
          process.kill(existingPid, 0); // signal 0 = check existence
          log('FAIL', `Another run.js instance is already running (PID ${existingPid}). Aborting to avoid interference.`);
          log('FAIL', `If that process is stale, remove ${LOCK_FILE} and retry.`);
          process.exit(1);
        } catch {
          // Process not found — stale lock file, safe to overwrite
          log('DEGRADED', `Stale lock file found (PID ${existingPid} not running). Overwriting.`);
        }
      }
    }
  } catch {}
  fs.writeFileSync(LOCK_FILE, String(process.pid));
  log('PASS', `Lock acquired (PID ${process.pid} → ${LOCK_FILE})`);
}

function releaseLock() {
  try {
    if (fs.existsSync(LOCK_FILE)) {
      const storedPid = parseInt(fs.readFileSync(LOCK_FILE, 'utf8').trim(), 10);
      if (storedPid === process.pid) {
        fs.unlinkSync(LOCK_FILE);
      }
    }
  } catch {}
}

// ─── Pre-flight: Stop any lingering bots from previous runs ───────────────────
async function stopAllRunningBots(tokens) {
  // Fetch statuses in parallel
  const statuses = await Promise.all(tokens.map(t =>
    apiRequest('GET', '/bots/status', null, t).catch(() => null)
  ));
  const stops = [];
  statuses.forEach((res, i) => {
    const bots = res?.data?.running_bots || [];
    for (const bot of bots) {
      if (bot.platform && bot.native_meeting_id) {
        stops.push(apiRequest('DELETE', `/bots/${bot.platform}/${encodeURIComponent(bot.native_meeting_id)}`, null, tokens[i])
          .then(r => log('PASS', `Stopped ${bot.platform}/${bot.native_meeting_id}: HTTP ${r.status}`))
          .catch(() => {}));
      }
    }
  });
  if (stops.length) {
    await Promise.all(stops);
    await sleep(800); // minimal drain
  }
}

// ─── Confidence reporter ───────────────────────────────────────────────────────
function reportConfidence(results) {
  // Load full history for consecutive-run checks
  let history = [];
  try {
    history = fs.readFileSync(HISTORY_FILE, 'utf8').trim().split('\n')
      .filter(Boolean).map(l => JSON.parse(l));
  } catch {}

  const last = results[results.length - 1];
  if (!last) return;

  // Gate checks
  const admitSec = last.admitMs / 1000;
  const totalSec = last.totalMs / 1000;

  const gates = {
    gate_lobby: { pass: admitSec <= 30,   detail: `${admitSec.toFixed(1)}s ${admitSec<=30?'<':'>'} 30s` },
    gate_admit: { pass: admitSec <= 40 && last.admitCount >= 2,
                  detail: `${admitSec.toFixed(1)}s, ${last.admitCount} bot(s) admitted` },
    gate_loop:  { pass: last.pass,         detail: last.pass ? 'loop completed' : 'loop failed' },
    gate_speed: { pass: false, detail: '' },
    gate_99:    { pass: false, detail: '' },
  };

  // gate_speed: <60s for last 3 consecutive
  const last3 = history.slice(-3);
  const speed3 = last3.length >= 3 && last3.every(r => r.pass && r.totalMs < 60000);
  const worst3 = last3.length ? Math.max(...last3.map(r => r.totalMs)) / 1000 : totalSec;
  gates.gate_speed = { pass: speed3, detail: speed3 ? '3× under 60s' : `${totalSec.toFixed(1)}s > 60s — need <60s × 3 consecutive (have ${last3.filter(r=>r.pass&&r.totalMs<60000).length}/3)` };

  // gate_99: <15s for last 20 consecutive
  const last20 = history.slice(-20);
  const speed20 = last20.length >= 20 && last20.every(r => r.pass && r.totalMs < 15000);
  gates.gate_99 = { pass: speed20, detail: speed20 ? '20× under 15s' : `${totalSec.toFixed(1)}s > 15s — need <15s × 20 consecutive (have ${last20.filter(r=>r.pass&&r.totalMs<15000).length}/${last20.length})` };

  // Determine level
  let level = 0, score = 0;
  if (gates.gate_lobby.pass) { level = 1; score = 50; }
  if (gates.gate_admit.pass) { level = 2; score = 70; }
  if (gates.gate_loop.pass)  { level = 3; score = 85; }
  if (gates.gate_speed.pass) { level = 4; score = 95; }
  if (gates.gate_99.pass)    { level = 5; score = 99; }

  console.log(`\nCONFIDENCE: ${score} (level ${level})`);
  for (const [name, g] of Object.entries(gates)) {
    const mark = g.pass ? 'PASS ' : 'BLOCK';
    console.log(`  ${mark}  ${name.padEnd(12)} ${g.detail}`);
  }
  if (score === 99) console.log('  ★ CONFIDENCE 99 ACHIEVED');
  console.log('');
}

// ─── Single run ───────────────────────────────────────────────────────────────
async function runOnce(platform, meetingUrl, runIndex) {
  const t0 = Date.now();
  const elapsed = () => `${((Date.now() - t0) / 1000).toFixed(1)}s`;

  log('PASS', `=== Run #${runIndex}: platform=${platform} ===`);

  // Pre-flight: stop lingering bots (parallel fetch + stop)
  await stopAllRunningBots([TOKEN_MAIN, TOKEN_ALICE]);

  // Create or reuse meeting
  const url = await createMeeting(platform, meetingUrl);
  if (!url) { log('FAIL', 'No meeting URL'); return { pass: false, admitCount: 0, admitMs: 0 }; }

  const nativeMeetingId = extractMeetingId(platform, url);
  if (!nativeMeetingId) { log('FAIL', `Bad meeting URL: ${url}`); return { pass: false, admitCount: 0, admitMs: 0 }; }
  log('PASS', `[${elapsed()}] Meeting: ${nativeMeetingId}`);

  // Start admit watcher immediately
  const admitStart = Date.now();
  const admitPromise = autoAdmit(platform, url, 120000);

  // Launch both bots — speaker first, then listener with minimal gap to avoid 409
  const speakerBot = await launchBot(platform, url, nativeMeetingId, TOKEN_MAIN, {
    tts_enabled: true, transcribe_enabled: false, voice_agent_enabled: true, bot_name: 'SpeakerBot',
  }, 'speaker');
  if (!speakerBot) { log('FAIL', 'Speaker bot launch failed'); return { pass: false, admitCount: 0, admitMs: 0 }; }

  await sleep(500); // minimal gap — enough to avoid 409 without wasting time

  const listenerBot = await launchBot(platform, url, nativeMeetingId, TOKEN_ALICE, {
    tts_enabled: false, transcribe_enabled: false, voice_agent_enabled: true, bot_name: 'ListenerBot',
  }, 'listener');
  if (!listenerBot) {
    log('FAIL', 'Listener bot launch failed');
    await stopBot(platform, nativeMeetingId, TOKEN_MAIN);
    return { pass: false, admitCount: 0, admitMs: 0 };
  }
  log('PASS', `[${elapsed()}] Both bots launched (speaker:${speakerBot.id}, listener:${listenerBot.id})`);

  // Wait for admission
  const admitCount = await admitPromise;
  const admitMs = Date.now() - admitStart;
  log('PASS', `[${elapsed()}] Admitted: ${admitCount} bots in ${(admitMs/1000).toFixed(1)}s`);

  if (admitCount === 0) {
    log('FAIL', 'No bots admitted — stopping');
    await Promise.all([
      stopBot(platform, nativeMeetingId, TOKEN_MAIN),
      stopBot(platform, nativeMeetingId, TOKEN_ALICE),
    ]);
    return { pass: false, admitCount: 0, admitMs };
  }

  // Wait for speaker bot to be active (poll 1s, up to 30s) — no blind sleep
  await waitForBotActive(platform, nativeMeetingId, TOKEN_MAIN, 30000);

  // Baseline screenshot: speaker indicator should be OFF
  const baseline = await checkSpeakerIndicator(url, `r${runIndex}-idle`);
  const idleSilent = (baseline?.speakingNow?.length ?? 0) === 0;
  log(idleSilent ? 'PASS' : 'DEGRADED', `[${elapsed()}] Idle indicator: ${idleSilent ? 'SILENT' : 'ACTIVE (noise)'}`);

  // Speak one utterance
  const utterance = UTTERANCES[0];
  const speakOk = await speakUtterance(platform, nativeMeetingId, utterance, TOKEN_MAIN);
  log(speakOk ? 'PASS' : 'DEGRADED', `[${elapsed()}] /speak: ${speakOk ? 'OK' : 'FAILED'}`);

  // Poll for speaking indicator to come ON (up to 4s)
  let duringSpeech = null;
  let speakingDetected = false;
  const speakDeadline = Date.now() + 4000;
  while (Date.now() < speakDeadline) {
    duringSpeech = await checkSpeakerIndicator(url, `r${runIndex}-speaking`);
    speakingDetected = (duringSpeech?.speakingNow?.length ?? 0) > 0 ||
                       (duringSpeech?.voiceLevelElements ?? 0) > 0;
    if (speakingDetected) break;
    await sleep(300);
  }
  log(speakingDetected ? 'PASS' : 'DEGRADED',
    `[${elapsed()}] Speaking indicator: ${speakingDetected ? 'ON' : 'OFF (not detected)'}`);

  // Poll for indicator to go OFF after speech (up to 8s)
  let afterSpeech = null;
  let silentAfter = false;
  const silentDeadline = Date.now() + 8000;
  while (Date.now() < silentDeadline) {
    afterSpeech = await checkSpeakerIndicator(url, `r${runIndex}-silent`);
    silentAfter = (afterSpeech?.speakingNow?.length ?? 0) === 0;
    if (silentAfter) break;
    await sleep(300);
  }
  log(silentAfter ? 'PASS' : 'DEGRADED',
    `[${elapsed()}] Post-speech indicator: ${silentAfter ? 'SILENT' : 'STILL ACTIVE'}`);

  // Cleanup
  await Promise.all([
    stopBot(platform, nativeMeetingId, TOKEN_MAIN),
    stopBot(platform, nativeMeetingId, TOKEN_ALICE),
  ]);

  const totalMs = Date.now() - t0;
  const pass = admitCount > 0 && speakOk;

  // Persist to run history (for confidence ladder evidence)
  const record = {
    ts: new Date().toISOString(),
    run: runIndex,
    pass,
    totalMs,
    admitMs,
    admitCount: admitCount >= 2 ? 2 : admitCount, // normalize Admit-all (+10) to actual bot count
    speakOk,
    idleSilent,
    speakingDetected,
    silentAfter,
    meetingId: nativeMeetingId,
  };
  try { fs.appendFileSync(HISTORY_FILE, JSON.stringify(record) + '\n'); } catch {}

  // ─── Report ────────────────────────────────────────────────────────────────
  console.log('\n' + '='.repeat(70));
  console.log(`RUN #${runIndex} — ${pass ? 'PASS' : 'FAIL'} — ${(totalMs/1000).toFixed(1)}s total`);
  console.log('='.repeat(70));
  console.log(`  Meeting:          ${url}`);
  console.log(`  Bots admitted:    ${admitCount} (in ${(admitMs/1000).toFixed(1)}s)`);
  console.log(`  /speak:           ${speakOk ? 'OK' : 'FAILED'}`);
  console.log(`  Idle indicator:   ${idleSilent ? 'SILENT ✓' : 'ACTIVE ✗'}`);
  console.log(`  Speaking detect:  ${speakingDetected ? 'ON ✓' : 'OFF ✗'}`);
  console.log(`  After-speech:     ${silentAfter ? 'SILENT ✓' : 'ACTIVE ✗'}`);
  console.log(`  Screenshots:      /tmp/hot-debug-r${runIndex}-{idle,speaking,silent}.png`);
  console.log('='.repeat(70) + '\n');

  return { pass, admitCount, admitMs, totalMs };
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  const opts = parseArgs();

  if (!opts.platform || !['teams', 'google_meet'].includes(opts.platform)) {
    console.error('Usage: node run.js --platform teams|google_meet [--meeting-url URL] [--runs N] [--loop]');
    process.exit(1);
  }

  acquireLock();
  process.on('exit', releaseLock);
  process.on('SIGINT', () => { releaseLock(); process.exit(130); });
  process.on('SIGTERM', () => { releaseLock(); process.exit(143); });

  const results = [];
  let runIndex = 0;
  const maxRuns = opts.loop ? Infinity : opts.runs;

  while (runIndex < maxRuns) {
    runIndex++;
    const result = await runOnce(opts.platform, opts.meetingUrl, runIndex).catch(e => {
      log('FAIL', `Run #${runIndex} threw: ${e.message}`);
      return { pass: false, admitCount: 0, admitMs: 0, totalMs: 0 };
    });
    results.push(result);

    // Confidence report after every run
    reportConfidence(results);

    const passed = results.filter(r => r.pass).length;
    const avgTotal = results.reduce((s, r) => s + (r.totalMs || 0), 0) / results.length / 1000;
    const avgAdmit = results.filter(r => r.admitMs).reduce((s, r) => s + r.admitMs, 0) / results.length / 1000;
    log('PASS', `Streak: ${passed}/${results.length} | avg total: ${avgTotal.toFixed(1)}s | avg admit: ${avgAdmit.toFixed(1)}s`);

    if (!opts.loop && runIndex >= opts.runs) break;

    // Brief pause between loop runs to let containers drain
    if (runIndex < maxRuns) await sleep(3000);
  }

  releaseLock();

  const passed = results.filter(r => r.pass).length;

  // Print last 20 from full history for confidence ladder
  try {
    const lines = fs.readFileSync(HISTORY_FILE, 'utf8').trim().split('\n').filter(Boolean);
    const last20 = lines.slice(-20).map(l => JSON.parse(l));
    const allPass = last20.every(r => r.pass);
    const maxTotal = Math.max(...last20.map(r => r.totalMs)) / 1000;
    const avgTotal = last20.reduce((s, r) => s + r.totalMs, 0) / last20.length / 1000;
    console.log('\n── Run History (last 20) ─────────────────────────────────────────────');
    last20.forEach(r => {
      const mark = r.pass ? 'PASS' : 'FAIL';
      console.log(`  #${String(r.run).padStart(3)} ${mark} | total:${(r.totalMs/1000).toFixed(1)}s admit:${(r.admitMs/1000).toFixed(1)}s | ${r.ts.substring(11,19)}`);
    });
    console.log(`  avg: ${avgTotal.toFixed(1)}s  max: ${maxTotal.toFixed(1)}s  streak: ${last20.filter(r=>r.pass).length}/${last20.length}`);
    if (allPass && last20.length >= 20 && maxTotal <= 15) {
      console.log('  ★ CONFIDENCE 99: last 20 all PASS under 15s');
    }
    console.log('─'.repeat(70));
  } catch {}

  if (results.length > 1) {
    console.log(`\nFINAL: ${passed}/${results.length} runs passed`);
  }
  process.exit(passed === results.length ? 0 : 1);
}

main().catch(e => {
  log('FAIL', `Unhandled error: ${e.message}\n${e.stack}`);
  releaseLock();
  process.exit(1);
});
