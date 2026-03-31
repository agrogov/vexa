#!/usr/bin/env node
// Watch for lobby notifications and admit participants.
// Works for both Google Meet and MS Teams (auto-detected from current URL).
// Usage: node admit-from-lobby.js [--cdp http://localhost:9222] [--timeout 60]
//
// Outputs: ADMITTED:<participant-name>
// Exits 0 on admit, 1 on timeout/error.

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');
const fs = require('fs');

const LOG_FILE = '/home/dima/dev/vexa/test.log';
const AGENT = 'browser-control/admit-from-lobby';

function log(level, msg) {
  const line = `[${new Date().toISOString()}] [${AGENT}] ${level}: ${msg}`;
  console.error(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function parseArgs() {
  const args = process.argv.slice(2);
  let cdp = process.env.CDP_URL || 'http://localhost:9222';
  let timeout = 60;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--cdp' && args[i + 1]) cdp = args[++i];
    if (args[i] === '--timeout' && args[i + 1]) timeout = parseInt(args[++i], 10);
  }
  return { cdp, timeout };
}

function detectPlatform(url) {
  if (url.includes('meet.google.com')) return 'google_meet';
  if (url.includes('teams.microsoft.com') || url.includes('teams.live.com')) return 'teams';
  return 'unknown';
}

async function admitGoogleMeet(page, deadline) {
  log('PASS', 'Polling for Google Meet lobby notification');

  while (Date.now() < deadline) {
    try {
      // Google Meet shows "Someone wants to join" or "Admit" button
      // Look for the admit button in various forms
      const admitBtn = page.locator(
        'button:has-text("Admit"), ' +
        'button:has-text("Accept"), ' +
        '[data-tooltip*="Admit"], ' +
        '[aria-label*="Admit"]'
      ).first();

      if (await admitBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        // Try to find the participant name nearby
        let participantName = 'unknown';
        try {
          // The notification usually contains the name before the admit button
          const notification = page.locator(
            '[data-participant-id], ' +
            '[class*="lobby"] [class*="name"], ' +
            'div:has(> button:has-text("Admit")) span'
          ).first();
          if (await notification.isVisible({ timeout: 500 }).catch(() => false)) {
            participantName = (await notification.textContent()).trim() || 'unknown';
          }
        } catch {}

        await admitBtn.click();
        log('PASS', `Admitted participant: ${participantName}`);
        console.log(`ADMITTED:${participantName}`);
        return true;
      }

      // Check for "Admit one guest" chip/notification (Google Meet 2025+ layout)
      try {
        const admitChip = await page.evaluate(() => {
          const all = document.querySelectorAll('*');
          for (const el of all) {
            if (el.textContent?.trim() === 'Admit one guest' && el.getBoundingClientRect().width < 300 && el.getBoundingClientRect().width > 0) {
              const rect = el.getBoundingClientRect();
              return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
            }
          }
          return null;
        });
        if (admitChip) {
          log('PASS', 'Found "Admit one guest" chip, clicking to open People panel');
          await page.mouse.click(admitChip.x, admitChip.y);
          await page.waitForTimeout(2000);
          // After opening the People panel, look for the Admit button again
          continue;
        }
      } catch {}

      // Also check for "View all" or "People" panel with lobby section
      try {
        const viewAll = page.locator('button:has-text("View all")').first();
        if (await viewAll.isVisible({ timeout: 500 }).catch(() => false)) {
          await viewAll.click();
          await page.waitForTimeout(1000);
          // After expanding, check for admit button again
          continue;
        }
      } catch {}

    } catch {}

    await page.waitForTimeout(2000);
  }

  return false;
}

async function admitTeams(page, deadline) {
  log('PASS', 'Polling for Teams lobby notification');

  while (Date.now() < deadline) {
    try {
      // Teams shows a toast notification with "Admit" or a lobby panel
      // Look for admit/accept buttons
      const admitBtn = page.locator(
        'button:has-text("Admit"), ' +
        'button:has-text("Accept"), ' +
        'button[data-tid*="lobby-admit"], ' +
        '[data-tid*="admit"], ' +
        'button:has-text("Let in"), ' +
        'button:has-text("Allow")'
      ).first();

      if (await admitBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        // Try to find participant name
        let participantName = 'unknown';
        try {
          const nameEl = page.locator(
            '[data-tid*="lobby"] [data-tid*="name"], ' +
            '[data-tid*="waiting"] span, ' +
            'div:has(> button:has-text("Admit")) [class*="displayName"]'
          ).first();
          if (await nameEl.isVisible({ timeout: 500 }).catch(() => false)) {
            participantName = (await nameEl.textContent()).trim() || 'unknown';
          }
        } catch {}

        await admitBtn.click();
        log('PASS', `Admitted participant: ${participantName}`);
        console.log(`ADMITTED:${participantName}`);
        return true;
      }

      // Check if there's a lobby notification banner to open
      try {
        const lobbyNotif = page.locator(
          '[data-tid*="lobby-notification"], ' +
          'button:has-text("View lobby"), ' +
          'button:has-text("in the lobby")'
        ).first();
        if (await lobbyNotif.isVisible({ timeout: 500 }).catch(() => false)) {
          await lobbyNotif.click();
          log('PASS', 'Opened lobby panel');
          await page.waitForTimeout(1000);
          continue;
        }
      } catch {}

      // Check for "Admit all" if multiple people are waiting
      try {
        const admitAll = page.locator('button:has-text("Admit all")').first();
        if (await admitAll.isVisible({ timeout: 500 }).catch(() => false)) {
          await admitAll.click();
          log('PASS', 'Clicked "Admit all"');
          console.log('ADMITTED:all');
          return true;
        }
      } catch {}

    } catch {}

    await page.waitForTimeout(2000);
  }

  return false;
}

async function main() {
  const { cdp, timeout } = parseArgs();
  let browser;

  try {
    log('PASS', `Connecting to CDP at ${cdp}`);
    browser = await chromium.connectOverCDP(cdp, { timeout: 15000 });
  } catch (err) {
    log('FAIL', `Cannot connect to CDP at ${cdp}: ${err.message}`);
    process.exit(1);
  }

  try {
    const contexts = browser.contexts();
    if (contexts.length === 0) {
      log('FAIL', 'No browser contexts found');
      process.exit(1);
    }
    const context = contexts[0];
    const pages = context.pages();
    if (pages.length === 0) {
      log('FAIL', 'No pages open in browser');
      process.exit(1);
    }

    // Find the page with an active meeting
    let page = null;
    let platform = 'unknown';
    for (const p of pages) {
      const url = p.url();
      const detected = detectPlatform(url);
      if (detected !== 'unknown') {
        page = p;
        platform = detected;
        break;
      }
    }

    if (!page) {
      log('FAIL', `No meeting page found. Open pages: ${pages.map(p => p.url()).join(', ')}`);
      process.exit(1);
    }

    log('PASS', `Detected platform: ${platform}, URL: ${page.url()}`);

    const deadline = Date.now() + timeout * 1000;
    let admitted = false;

    if (platform === 'google_meet') {
      admitted = await admitGoogleMeet(page, deadline);
    } else if (platform === 'teams') {
      admitted = await admitTeams(page, deadline);
    }

    if (!admitted) {
      log('FAIL', `Timed out after ${timeout}s waiting for lobby participant`);
      process.exit(1);
    }

  } catch (err) {
    log('FAIL', `Error in lobby admission: ${err.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  log('FAIL', `Unhandled error: ${err.message}`);
  process.exit(1);
});
