#!/usr/bin/env node
// Create a Google Meet meeting via CDP on an authenticated browser.
// Usage: node create-google-meet.js [--cdp http://localhost:9222]
//
// Outputs: MEETING:https://meet.google.com/xxx-yyyy-zzz
// Exits 0 on success, 1 on failure.

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');
const fs = require('fs');

const LOG_FILE = '/home/dima/dev/vexa/test.log';
const AGENT = 'browser-control/create-google-meet';

function log(level, msg) {
  const line = `[${new Date().toISOString()}] [${AGENT}] ${level}: ${msg}`;
  console.error(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function parseArgs() {
  const args = process.argv.slice(2);
  let cdp = process.env.CDP_URL || 'http://localhost:9222';
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--cdp' && args[i + 1]) cdp = args[++i];
  }
  return { cdp };
}

async function main() {
  const { cdp } = parseArgs();
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
      log('FAIL', 'No browser contexts found. Is Chromium running?');
      process.exit(1);
    }
    const context = contexts[0];
    const page = context.pages()[0] || await context.newPage();

    log('PASS', 'Navigating to meet.new');
    await page.goto('https://meet.new', { waitUntil: 'networkidle', timeout: 30000 });

    const url = page.url();

    // Check if sign-in is required
    if (url.includes('accounts.google.com') || url.includes('signin')) {
      log('FAIL', `Google sign-in required. Current URL: ${url}. Sign in via VNC first.`);
      console.log(`FAIL:AUTH_REQUIRED`);
      process.exit(1);
    }

    // Wait for meeting page to stabilize
    await page.waitForTimeout(3000);

    // Dismiss "Got it" dialog if present
    try {
      const gotIt = page.locator('button:has-text("Got it")');
      if (await gotIt.isVisible({ timeout: 2000 }).catch(() => false)) {
        await gotIt.click();
        log('PASS', 'Dismissed "Got it" dialog');
      }
    } catch {}

    // Dismiss any other overlay dialogs
    try {
      const dismiss = page.locator('button:has-text("Dismiss")');
      if (await dismiss.isVisible({ timeout: 1000 }).catch(() => false)) {
        await dismiss.click();
        log('PASS', 'Dismissed overlay dialog');
      }
    } catch {}

    // Dismiss microphone/camera permission dialogs
    try {
      const close = page.locator('[aria-label="Close"]').first();
      if (await close.isVisible({ timeout: 1000 }).catch(() => false)) {
        await close.click();
        log('PASS', 'Closed permission dialog');
      }
    } catch {}

    const meetingUrl = page.url();

    // Validate it looks like a Google Meet URL
    if (!meetingUrl.includes('meet.google.com/')) {
      log('FAIL', `Unexpected URL after navigation: ${meetingUrl}`);
      process.exit(1);
    }

    // Extract clean meeting URL (strip query params)
    const meetMatch = meetingUrl.match(/(https:\/\/meet\.google\.com\/[a-z]{3}-[a-z]{4}-[a-z]{3})/);
    const cleanUrl = meetMatch ? meetMatch[1] : meetingUrl.split('?')[0];

    log('PASS', `Meeting created: ${cleanUrl}`);
    console.log(`MEETING:${cleanUrl}`);

  } catch (err) {
    log('FAIL', `Error creating meeting: ${err.message}`);
    process.exit(1);
  } finally {
    // Disconnect CDP without closing the browser
    await browser.close();
  }
}

main().catch(err => {
  log('FAIL', `Unhandled error: ${err.message}`);
  process.exit(1);
});
