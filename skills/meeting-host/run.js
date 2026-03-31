#!/usr/bin/env node
/**
 * meeting_host — create a Teams meeting and auto-admit everyone who arrives
 *
 * Usage:
 *   node run.js                        # create new meeting, print URL, admit loop
 *   node run.js --meeting-url <URL>    # reuse existing meeting, admit loop
 */

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');

const CDP_URL = 'http://localhost:9222';

// ─── Connect to organizer browser ────────────────────────────────────────────
let browser, page;

async function connect() {
  browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  const ctx = browser.contexts()[0];
  page = ctx.pages()[0] || await ctx.newPage();
  console.log(`[host] Connected to organizer browser: ${page.url()}`);
}

// ─── Create meeting ───────────────────────────────────────────────────────────
async function createMeeting() {
  const currentUrl = page.url();
  if (!currentUrl.includes('teams.microsoft.com') && !currentUrl.includes('teams.live.com')) {
    await page.goto('https://teams.live.com/v2/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  }

  // Intercept meeting URL from API response
  let meetingUrl = null;
  const onResponse = async (res) => {
    const url = res.url();
    if (url.includes('schedulingService/create') || url.includes('privateMeeting')) {
      try {
        const body = await res.text();
        const data = JSON.parse(body);
        const join = data?.value?.links?.join || data?.links?.join || data?.meetingUrl;
        if (join?.includes('teams.live.com/meet/')) meetingUrl = join;
      } catch {}
    }
  };
  page.on('response', onResponse);

  // Dismiss active call if any
  await page.evaluate(() => document.querySelector('[data-tid="hangup-main-btn"]')?.click()).catch(() => {});
  await page.waitForFunction(() => !document.querySelector('[data-tid="hangup-main-btn"]'), { timeout: 5000 }).catch(() => {});

  // Meet sidebar → Create a meeting link
  await page.waitForSelector('button[aria-label="Meet"]', { timeout: 15000 });
  await page.evaluate(() => document.querySelector('button[aria-label="Meet"]')?.click());

  await page.waitForFunction(
    () => !!document.querySelector('[data-tid="create-meeting-link"]') ||
          !!Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create a meeting link' && b.getBoundingClientRect().width > 0),
    { timeout: 8000 }
  ).catch(() => {});
  await page.evaluate(() => {
    const el = document.querySelector('[data-tid="create-meeting-link"]') ||
      Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create a meeting link');
    el?.click();
  });

  // Create and copy link
  await page.waitForFunction(
    () => !!Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create and copy link' && b.getBoundingClientRect().width > 0),
    { timeout: 8000 }
  ).catch(() => {});
  await page.evaluate(() => {
    Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Create and copy link')?.click();
  });

  // Wait for URL from API response
  const deadline = Date.now() + 10000;
  while (!meetingUrl && Date.now() < deadline) await new Promise(r => setTimeout(r, 100));
  page.off('response', onResponse);

  if (!meetingUrl) throw new Error('Could not capture meeting URL from API response');

  // Join as organizer
  await page.waitForFunction(
    () => !!Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Join' && b.getBoundingClientRect().width > 0),
    { timeout: 8000 }
  ).catch(() => {});
  await page.evaluate(() => {
    Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Join' && b.getBoundingClientRect().width > 0)?.click();
  });

  await page.waitForFunction(
    () => !!document.querySelector('[data-tid="prejoin-join-button"]') || !!document.querySelector('[data-tid="hangup-main-btn"]'),
    { timeout: 15000 }
  ).catch(() => {});
  if (!await page.evaluate(() => !!document.querySelector('[data-tid="hangup-main-btn"]'))) {
    await page.evaluate(() => {
      (document.querySelector('[data-tid="prejoin-join-button"]') ||
       Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Join now'))?.click();
    });
    await page.waitForSelector('[data-tid="hangup-main-btn"]', { timeout: 15000 }).catch(() => {});
  }

  return meetingUrl.trim().replace(/[,;.]+$/, '');
}

// ─── Auto-admit loop ──────────────────────────────────────────────────────────
// MutationObserver catches DOM changes instantly.
// Handles Teams two-step flow: "View Lobby" → "Admit" / "Admit all"
async function startAdmitLoop() {
  await page.evaluate(() => {
    function admit() {
      for (const el of document.querySelectorAll('button, [role="button"]')) {
        const text = (el.textContent || el.getAttribute('aria-label') || '').trim().toLowerCase();
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0) continue;
        if (text === 'view lobby' || text.includes('view lobby')) { el.click(); continue; }
        if (text.includes('admit all'))  { el.click(); console.log('[host] Admitted all'); continue; }
        if (text.includes('admit') && !text.includes('admitting')) { el.click(); console.log('[host] Admitted:', el.textContent?.trim()); }
      }
    }
    const obs = new MutationObserver(admit);
    obs.observe(document.body, { childList: true, subtree: true, attributes: true });
    admit(); // run once immediately
    window.__meetingHostObserver = obs;
    console.log('[host] Admit observer active');
  });
  console.log('[host] Auto-admit running (MutationObserver + backup poll)');

  // Backup poll every 2s
  const poll = setInterval(async () => {
    await page.evaluate(() => {
      for (const el of document.querySelectorAll('button, [role="button"]')) {
        const text = (el.textContent || el.getAttribute('aria-label') || '').trim().toLowerCase();
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0) continue;
        if (text === 'view lobby' || text.includes('view lobby')) el.click();
        else if (text.includes('admit all')) { el.click(); console.log('[host] Poll: Admitted all'); }
        else if (text.includes('admit') && !text.includes('admitting')) { el.click(); console.log('[host] Poll: Admitted'); }
      }
    }).catch(() => {});
  }, 2000);

  return poll;
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  let meetingUrl = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--meeting-url' && args[i+1]) meetingUrl = args[++i];
  }

  await connect();

  if (!meetingUrl) {
    console.log('[host] Creating meeting...');
    meetingUrl = await createMeeting();
  } else {
    console.log('[host] Using existing meeting');
  }

  console.log('\n' + '='.repeat(60));
  console.log('MEETING URL:', meetingUrl);
  console.log('='.repeat(60) + '\n');

  const poll = await startAdmitLoop();

  // Run until Ctrl+C
  process.on('SIGINT', () => {
    clearInterval(poll);
    page.evaluate(() => window.__meetingHostObserver?.disconnect()).catch(() => {});
    console.log('\n[host] Stopped');
    process.exit(0);
  });

  // Keep alive
  await new Promise(() => {});
}

main().catch(e => { console.error('[host] Error:', e.message); process.exit(1); });
