#!/usr/bin/env node
// Full automated test meeting loop:
// 1. Create meeting (Google Meet or Teams)
// 2. Start playing audio in background
// 3. Output meeting URL (for bot to join)
// 4. Poll for lobby notification, admit when bot appears
// 5. Wait for specified duration
// 6. Stop audio, leave meeting
// 7. Output TEST_COMPLETE
//
// Usage: node run-test-meeting.js --platform google_meet|teams [options]
//   --cdp URL          CDP endpoint (default: http://localhost:9222)
//   --platform         google_meet or teams (required)
//   --audio FILE       WAV file to play (optional)
//   --duration SECS    How long to stay in meeting (default: 60)
//   --container NAME   Docker container for audio playback (default: vexa-host)
//   --admit-timeout S  How long to wait for lobby (default: 120)
//   --no-admit         Skip lobby admission polling
//
// Outputs: MEETING:..., ADMITTED:..., TEST_COMPLETE

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');
const { execSync, spawn, fork } = require('child_process');
const fs = require('fs');
const path = require('path');

const LOG_FILE = '/home/dima/dev/vexa/test.log';
const AGENT = 'browser-control/run-test-meeting';
const SCRIPTS_DIR = __dirname;

function log(level, msg) {
  const line = `[${new Date().toISOString()}] [${AGENT}] ${level}: ${msg}`;
  console.error(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    cdp: process.env.CDP_URL || 'http://localhost:9222',
    platform: null,
    audio: null,
    duration: 60,
    container: process.env.CONTAINER_NAME || 'vexa-host',
    admitTimeout: 120,
    noAdmit: false,
    meetingName: 'Vexa Test Meeting',
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--cdp' && args[i + 1]) { opts.cdp = args[++i]; continue; }
    if (args[i] === '--platform' && args[i + 1]) { opts.platform = args[++i]; continue; }
    if (args[i] === '--audio' && args[i + 1]) { opts.audio = args[++i]; continue; }
    if (args[i] === '--duration' && args[i + 1]) { opts.duration = parseInt(args[++i], 10); continue; }
    if (args[i] === '--container' && args[i + 1]) { opts.container = args[++i]; continue; }
    if (args[i] === '--admit-timeout' && args[i + 1]) { opts.admitTimeout = parseInt(args[++i], 10); continue; }
    if (args[i] === '--no-admit') { opts.noAdmit = true; continue; }
    if (args[i] === '--name' && args[i + 1]) { opts.meetingName = args[++i]; continue; }
  }

  return opts;
}

function runScript(scriptName, extraArgs = []) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(SCRIPTS_DIR, scriptName);
    const proc = spawn('node', [scriptPath, ...extraArgs], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', d => { stdout += d.toString(); });
    proc.stderr.on('data', d => {
      const text = d.toString();
      stderr += text;
      // Forward stderr for visibility
      process.stderr.write(text);
    });

    proc.on('close', code => {
      resolve({ code, stdout: stdout.trim(), stderr: stderr.trim() });
    });

    proc.on('error', reject);
  });
}

function spawnScript(scriptName, extraArgs = []) {
  const scriptPath = path.join(SCRIPTS_DIR, scriptName);
  const proc = spawn('node', [scriptPath, ...extraArgs], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  proc.stderr.on('data', d => process.stderr.write(d));
  proc.stdout.on('data', d => process.stdout.write(d));

  return proc;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const opts = parseArgs();

  if (!opts.platform || !['google_meet', 'teams'].includes(opts.platform)) {
    console.error('Usage: node run-test-meeting.js --platform google_meet|teams [options]');
    console.error('  --platform is required: google_meet or teams');
    process.exit(1);
  }

  log('PASS', `Starting test meeting: platform=${opts.platform}, duration=${opts.duration}s`);

  // Step 1: Create meeting
  const createScript = opts.platform === 'google_meet'
    ? 'create-google-meet.js'
    : 'create-teams-meeting.js';

  const createArgs = ['--cdp', opts.cdp];
  if (opts.platform === 'teams') {
    createArgs.push('--name', opts.meetingName);
  }

  log('PASS', `Creating ${opts.platform} meeting`);
  const createResult = await runScript(createScript, createArgs);

  if (createResult.code !== 0) {
    log('FAIL', `Meeting creation failed (exit ${createResult.code})`);
    process.exit(1);
  }

  // Extract meeting URL from stdout
  const meetingLine = createResult.stdout.split('\n').find(l => l.startsWith('MEETING:'));
  if (!meetingLine) {
    log('FAIL', `No MEETING: line in output: ${createResult.stdout}`);
    process.exit(1);
  }

  const meetingUrl = meetingLine.replace('MEETING:', '');
  log('PASS', `Meeting created: ${meetingUrl}`);
  console.log(`MEETING:${meetingUrl}`);

  // Step 2: Start audio playback in background (if specified)
  let audioProc = null;
  if (opts.audio) {
    log('PASS', `Starting audio playback: ${opts.audio}`);
    audioProc = spawnScript('play-audio.js', [
      opts.audio,
      '--container', opts.container,
    ]);
  }

  // Step 3: Wait a moment for bot to join, then poll for lobby admission
  if (!opts.noAdmit) {
    log('PASS', `Waiting for lobby participant (timeout: ${opts.admitTimeout}s)`);
    const admitResult = await runScript('admit-from-lobby.js', [
      '--cdp', opts.cdp,
      '--timeout', String(opts.admitTimeout),
    ]);

    if (admitResult.code === 0) {
      const admitLine = admitResult.stdout.split('\n').find(l => l.startsWith('ADMITTED:'));
      if (admitLine) {
        console.log(admitLine);
      }
    } else {
      log('DEGRADED', `Lobby admission timed out or failed — bot may have joined without lobby`);
    }
  }

  // Step 4: Wait for specified duration
  log('PASS', `Meeting active. Waiting ${opts.duration}s...`);
  await sleep(opts.duration * 1000);

  // Step 5: Stop audio
  if (audioProc && !audioProc.killed) {
    log('PASS', 'Stopping audio playback');
    audioProc.kill('SIGTERM');
  }

  // Step 6: Leave meeting
  log('PASS', 'Leaving meeting');
  let browser;
  try {
    browser = await chromium.connectOverCDP(opts.cdp, { timeout: 15000 });
    const contexts = browser.contexts();
    if (contexts.length > 0) {
      const context = contexts[0];
      for (const page of context.pages()) {
        const url = page.url();

        if (url.includes('meet.google.com')) {
          // Google Meet: click the red hangup button
          try {
            const hangup = page.locator('[aria-label="Leave call"], button[data-tooltip="Leave call"]').first();
            if (await hangup.isVisible({ timeout: 3000 }).catch(() => false)) {
              await hangup.click();
              log('PASS', 'Left Google Meet');
            }
          } catch {}
        }

        if (url.includes('teams.microsoft.com') || url.includes('teams.live.com')) {
          // Teams: click the hangup button
          try {
            const hangup = page.locator('button[data-tid*="hangup"], button:has-text("Leave"), [aria-label="Leave"]').first();
            if (await hangup.isVisible({ timeout: 3000 }).catch(() => false)) {
              await hangup.click();
              log('PASS', 'Left Teams meeting');
            }
          } catch {}
        }
      }
    }
  } catch (err) {
    log('DEGRADED', `Could not leave meeting cleanly: ${err.message}`);
  } finally {
    if (browser) await browser.close();
  }

  log('PASS', 'Test meeting complete');
  console.log('TEST_COMPLETE');
}

main().catch(err => {
  log('FAIL', `Unhandled error: ${err.message}`);
  process.exit(1);
});
