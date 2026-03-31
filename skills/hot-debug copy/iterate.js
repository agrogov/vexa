#!/usr/bin/env node
/**
 * Minimal iteration loop: create meeting → launch listener bot → admit → verify active
 * Run 3 clean iterations with no human intervention.
 * Usage: node iterate.js [--iterations 3]
 */

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

// ─── Config ───────────────────────────────────────────────────────────────────
const CDP_URL    = 'http://localhost:9222';
const API_BASE   = 'http://localhost:8056';
const TOKEN_MAIN = 'vxa_user_mZbCdNnQwmzU2rjyGcyCjj0is8Mx75ljtHgHsM2L';
const LOG_FILE   = '/home/dima/dev/vexa/test.log';
const SCRIPTS_DIR = '/home/dima/dev/vexa/features/browser-control/scripts';

// ─── Helpers ──────────────────────────────────────────────────────────────────
function log(level, msg) {
  const line = `[${new Date().toISOString()}] [hot-debug/iterate] ${level}: ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function parseArgs() {
  const args = process.argv.slice(2);
  let iterations = 3;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--iterations' && args[i+1]) iterations = parseInt(args[++i], 10);
  }
  return { iterations };
}

function apiRequest(method, path, body, token) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const headers = { 'X-API-Key': token || TOKEN_MAIN, 'Content-Type': 'application/json' };
    if (data) headers['Content-Length'] = Buffer.byteLength(data);
    const url = new URL(API_BASE + path);
    const req = http.request({
      hostname: url.hostname, port: url.port || 80,
      path: url.pathname + (url.search || ''), method, headers,
    }, (res) => {
      let buf = '';
      res.on('data', d => buf += d);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(buf) }); }
        catch { resolve({ status: res.statusCode, data: buf }); }
      });
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

function runScript(scriptName, extraArgs = []) {
  const scriptPath = `${SCRIPTS_DIR}/${scriptName}`;
  return new Promise((resolve) => {
    const proc = spawn('node', [scriptPath, ...extraArgs], { stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    proc.stdout.on('data', d => { stdout += d.toString(); process.stdout.write(d); });
    proc.stderr.on('data', d => { stderr += d.toString(); process.stderr.write(d); });
    proc.on('close', code => resolve({ code, stdout: stdout.trim(), stderr: stderr.trim() }));
    proc.on('error', e => resolve({ code: 1, stdout: '', stderr: e.message }));
  });
}

// ─── Step 1: Create meeting ────────────────────────────────────────────────────
async function createMeeting() {
  log('PASS', 'Creating Teams meeting via CDP...');
  const result = await runScript('create-teams-meeting.js', ['--cdp', CDP_URL]);
  if (result.code !== 0) {
    log('FAIL', `Meeting creation failed (exit ${result.code}): ${result.stderr.substring(0, 200)}`);
    return null;
  }
  const line = (result.stdout + '\n' + result.stderr).split('\n').find(l => l.startsWith('MEETING:'));
  if (!line) {
    log('FAIL', 'No MEETING: line in script output');
    return null;
  }
  const url = line.replace('MEETING:', '').trim();
  log('PASS', `Meeting URL: ${url}`);
  return url;
}

// ─── Step 2: Extract native meeting ID ────────────────────────────────────────
function extractMeetingId(meetingUrl) {
  const m = meetingUrl.match(/\/meet\/([^?&/]+)/);
  return m ? m[1] : null;
}

// ─── Step 3: Launch listener bot ──────────────────────────────────────────────
async function launchListenerBot(meetingUrl, nativeMeetingId) {
  log('PASS', `Launching listener bot for ${nativeMeetingId}...`);
  const body = {
    platform: 'teams',
    native_meeting_id: nativeMeetingId,
    meeting_url: meetingUrl,
    voice_agent_enabled: true,
  };
  const res = await apiRequest('POST', '/bots', body, TOKEN_MAIN);
  log(res.status === 200 || res.status === 201 ? 'PASS' : 'FAIL',
    `Launch bot: HTTP ${res.status} → ${JSON.stringify(res.data).substring(0, 300)}`);
  if (res.status !== 200 && res.status !== 201) return null;
  return res.data;
}

// ─── Step 4: Auto-admit from lobby ────────────────────────────────────────────
async function autoAdmit(timeoutMs = 120000) {
  log('PASS', `Starting auto-admit watcher (${timeoutMs/1000}s)...`);
  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  } catch(e) {
    log('FAIL', `CDP connect for admit failed: ${e.message}`);
    return 0;
  }
  const ctx = browser.contexts()[0];
  const deadline = Date.now() + timeoutMs;
  let admitCount = 0;

  while (Date.now() < deadline) {
    try {
      const pages = ctx.pages();
      for (const page of pages) {
        const pageUrl = page.url();
        if (!pageUrl.includes('teams.live.com') && !pageUrl.includes('teams.microsoft.com')) continue;

        // First open lobby panel if there's a notification banner
        await page.evaluate(() => {
          const selectors = [
            '[data-tid*="lobby-notification"]',
            'button[data-tid*="lobby-notification"]',
          ];
          for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.getBoundingClientRect().width > 0) { el.click(); return; }
          }
          // Try text-based banner
          const all = document.querySelectorAll('button, [role="button"]');
          for (const el of all) {
            const t = el.textContent?.trim();
            if ((t === 'View lobby' || t?.includes('in the lobby')) && el.getBoundingClientRect().width > 0) {
              el.click(); return;
            }
          }
        }).catch(() => {});

        // Try to admit
        const admitted = await page.evaluate(() => {
          // CSS has-text selectors don't work in querySelectorAll; iterate manually
          const buttonTexts = ['Admit', 'Accept', 'Allow', 'Let in', 'Admit all'];
          const dataTids = ['lobby-admit', 'admit'];

          // Check data-tid first
          for (const tid of dataTids) {
            const els = document.querySelectorAll(`[data-tid*="${tid}"]`);
            for (const el of els) {
              if (el.tagName === 'BUTTON' && el.getBoundingClientRect().width > 0) {
                el.click();
                return el.textContent?.trim() || 'admitted-by-tid';
              }
            }
          }

          // Check by button text
          const buttons = document.querySelectorAll('button');
          for (const btn of buttons) {
            const text = btn.textContent?.trim();
            if (buttonTexts.includes(text) && btn.getBoundingClientRect().width > 0) {
              btn.click();
              return text;
            }
          }
          return null;
        }).catch(() => null);

        if (admitted) {
          admitCount++;
          log('PASS', `Admitted #${admitCount}: "${admitted}"`);
          if (admitCount >= 1) break;
        }
      }
    } catch {}

    if (admitCount >= 1) break;
    await sleep(500);
  }

  await browser.close();

  if (admitCount === 0) {
    log('DEGRADED', `No bots admitted in ${timeoutMs/1000}s`);
  }
  return admitCount;
}

// ─── Step 5: Poll bot status until active ─────────────────────────────────────
// Uses GET /meetings which returns all meetings sorted newest first.
// We find the one with matching native_meeting_id and check status.
async function waitForActive(nativeMeetingId, timeoutMs = 90000) {
  log('PASS', `Polling bot status for ${nativeMeetingId} (timeout: ${timeoutMs/1000}s)...`);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await apiRequest('GET', '/meetings', null, TOKEN_MAIN);
      if (res.status === 200) {
        const meetings = Array.isArray(res.data) ? res.data : (res.data.meetings || []);
        const meeting = meetings.find(m => m.native_meeting_id === nativeMeetingId);
        if (meeting) {
          const status = meeting.status;
          log('PASS', `Bot status: ${status}`);
          if (status === 'active') return status;
          if (status === 'error' || status === 'failed' || status === 'ended') {
            log('FAIL', `Bot reached terminal state: ${status}`);
            return null;
          }
        } else {
          log('PASS', `Meeting ${nativeMeetingId} not found in list yet...`);
        }
      }
    } catch (e) {
      log('DEGRADED', `Status poll error: ${e.message}`);
    }
    await sleep(3000);
  }
  log('FAIL', `Bot never reached active in ${timeoutMs/1000}s`);
  return null;
}

// ─── Step 6: Stop bot ─────────────────────────────────────────────────────────
async function stopBot(nativeMeetingId) {
  try {
    const encodedId = encodeURIComponent(nativeMeetingId);
    // DELETE /bots/{platform}/{native_meeting_id} stops the bot
    const res = await apiRequest('DELETE', `/bots/teams/${encodedId}`, null, TOKEN_MAIN);
    log(res.status === 200 || res.status === 204 ? 'PASS' : 'DEGRADED',
      `Stop bot: HTTP ${res.status}`);
  } catch (e) {
    log('DEGRADED', `Stop bot failed: ${e.message}`);
  }
}

// ─── Navigate browser back to Teams hub ───────────────────────────────────────
async function resetBrowserToTeamsHub() {
  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
    const ctx = browser.contexts()[0];
    const pages = ctx.pages();
    for (const p of pages) {
      if (p.url().includes('teams.live.com') || p.url().includes('teams.microsoft.com')) {
        await p.goto('https://teams.live.com/v2/', { waitUntil: 'load', timeout: 20000 });
        await p.waitForTimeout(3000);
        log('PASS', 'Navigated browser back to Teams hub');
        break;
      }
    }
  } catch(e) {
    log('DEGRADED', `Browser reset failed: ${e.message}`);
  } finally {
    if (browser) await browser.close();
  }
}

// ─── Run one iteration ────────────────────────────────────────────────────────
async function runIteration(n) {
  const startMs = Date.now();
  log('PASS', `\n${'='.repeat(60)}\nITERATION ${n} START\n${'='.repeat(60)}`);

  // 1. Create meeting
  const meetingUrl = await createMeeting();
  if (!meetingUrl) return { pass: false, reason: 'Meeting creation failed' };

  const nativeMeetingId = extractMeetingId(meetingUrl);
  if (!nativeMeetingId) return { pass: false, reason: `Cannot extract ID from: ${meetingUrl}` };
  log('PASS', `Native meeting ID: ${nativeMeetingId}`);

  // 2. Start admit watcher BEFORE launching bot (bot takes ~25s to reach lobby)
  const admitPromise = autoAdmit(120000);

  // 3. Launch listener bot
  const bot = await launchListenerBot(meetingUrl, nativeMeetingId);
  if (!bot) {
    // Let admit watcher finish with shorter timeout
    await admitPromise;
    return { pass: false, reason: 'Bot launch failed' };
  }

  // 4. Wait for admit (bot needs ~25s to reach lobby)
  const admitCount = await admitPromise;
  log('PASS', `Admit count: ${admitCount}`);

  // 5. Poll for active status
  const status = await waitForActive(nativeMeetingId, 90000);

  const elapsedS = Math.round((Date.now() - startMs) / 1000);
  const pass = status !== null;

  log(pass ? 'PASS' : 'FAIL',
    `Iteration ${n}: ${pass ? 'PASS' : 'FAIL'} (status=${status}, admitted=${admitCount}, elapsed=${elapsedS}s)`);

  // 6. Stop bot
  await stopBot(nativeMeetingId);
  await sleep(3000);

  // 7. Reset browser for next iteration
  await resetBrowserToTeamsHub();
  await sleep(2000);

  return { pass, reason: pass ? `status=${status}` : `status=${status}, admitted=${admitCount}`, elapsedS };
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  const { iterations } = parseArgs();
  log('PASS', `=== Teams Bot Iteration Test: ${iterations} iterations ===`);

  const results = [];
  for (let i = 1; i <= iterations; i++) {
    const result = await runIteration(i);
    results.push({ iteration: i, ...result });
    if (i < iterations) {
      log('PASS', `Waiting 5s before next iteration...`);
      await sleep(5000);
    }
  }

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('ITERATION TEST SUMMARY');
  console.log('='.repeat(60));
  let allPass = true;
  for (const r of results) {
    const icon = r.pass ? 'PASS' : 'FAIL';
    console.log(`  Iteration ${r.iteration}: ${icon} — ${r.reason} (${r.elapsedS}s)`);
    if (!r.pass) allPass = false;
  }
  console.log('='.repeat(60));
  console.log(`Overall: ${allPass ? 'ALL PASS' : 'SOME FAILED'}`);
  console.log('='.repeat(60) + '\n');

  process.exit(allPass ? 0 : 1);
}

main().catch(e => {
  log('FAIL', `Unhandled error: ${e.message}\n${e.stack}`);
  process.exit(1);
});
