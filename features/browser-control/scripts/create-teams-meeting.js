#!/usr/bin/env node
// Create an MS Teams meeting via CDP on an authenticated browser.
// Usage: node create-teams-meeting.js [--cdp http://localhost:9222] [--name "Test Meeting"]
//
// Outputs: MEETING:https://teams.live.com/meet/xxx?p=yyy
// Exits 0 on success, 1 on failure.
//
// Strategy: intercept the /schedulingService/create API response which contains
// links.join with the real meeting URL. No clipboard needed.

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');
const fs = require('fs');

const LOG_FILE = '/home/dima/dev/vexa/test.log';
const AGENT = 'browser-control/create-teams-meeting';

function log(level, msg) {
  const line = `[${new Date().toISOString()}] [${AGENT}] ${level}: ${msg}`;
  console.error(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function parseArgs() {
  const args = process.argv.slice(2);
  let cdp = process.env.CDP_URL || 'http://localhost:9222';
  let name = 'Vexa Test Meeting';
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--cdp' && args[i + 1]) cdp = args[++i];
    if (args[i] === '--name' && args[i + 1]) name = args[++i];
  }
  return { cdp, name };
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function main() {
  const { cdp, name } = parseArgs();
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

    // Grant clipboard permissions so we can read the copied meeting URL
    await context.grantPermissions(['clipboard-read', 'clipboard-write']).catch(() => {});

    // Check if sign-in is required
    const url = page.url();
    if (url.includes('login.microsoftonline.com') || url.includes('login.live.com')) {
      log('FAIL', `Microsoft sign-in required. Current URL: ${url}. Sign in via VNC first.`);
      console.log('FAIL:AUTH_REQUIRED');
      process.exit(1);
    }

    // Set up API response interceptor BEFORE clicking anything.
    // The /schedulingService/create endpoint returns the meeting URL in links.join
    let apiMeetingUrl = null;
    const responsePromise = new Promise((resolve) => {
      page.on('response', async (res) => {
        const resUrl = res.url();
        if (resUrl.includes('schedulingService/create') || resUrl.includes('privateMeeting')) {
          try {
            const body = await res.text();
            log('PASS', `Scheduling API response (${res.status()}): ${body.substring(0, 500)}`);
            const data = JSON.parse(body);
            const joinUrl = data?.value?.links?.join || data?.links?.join || data?.meetingUrl;
            if (joinUrl && joinUrl.includes('teams')) {
              log('PASS', `Extracted meeting URL from API: ${joinUrl}`);
              resolve(joinUrl);
            }
          } catch (e) {
            log('DEGRADED', `Could not parse scheduling API response: ${e.message}`);
          }
        }
      });
    });

    // Navigate to Meet section if not already there
    log('PASS', `Current URL: ${page.url()}`);
    if (!page.url().includes('teams.live.com') && !page.url().includes('teams.microsoft.com')) {
      log('PASS', 'Navigating to Teams');
      await page.goto('https://teams.live.com/v2/', { waitUntil: 'load', timeout: 30000 });
      await sleep(4000);
    }

    // Click Meet in sidebar
    log('PASS', 'Clicking Meet sidebar button');
    const meetClicked = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const meetBtn = btns.find(b => b.textContent?.trim() === 'Meet');
      if (meetBtn) { meetBtn.click(); return true; }
      return false;
    });

    if (!meetClicked) {
      log('FAIL', 'Could not find Meet sidebar button');
      await page.screenshot({ path: '/tmp/teams-create-fail-meet.png' });
      process.exit(1);
    }
    await sleep(2000);

    // Leave any active or held meetings before creating a new one.
    // Teams can have a main meeting + a "held" meeting — both must be ended.
    const meetingState = await page.evaluate(() => {
      const inMain = !!document.querySelector('[data-tid="hangup-main-btn"]');
      const heldEndBtn = Array.from(document.querySelectorAll('button')).find(b =>
        b.getAttribute('title')?.toLowerCase().includes('end call')
      );
      return { inMain, hasHeld: !!heldEndBtn };
    });

    if (meetingState.inMain || meetingState.hasHeld) {
      log('PASS', `Leaving meetings (inMain=${meetingState.inMain}, hasHeld=${meetingState.hasHeld})...`);

      // Leave the main active meeting first
      if (meetingState.inMain) {
        await page.evaluate(() => {
          const leaveBtn = document.querySelector('[data-tid="hangup-main-btn"]');
          if (leaveBtn) leaveBtn.click();
        });
        await sleep(2000);
      }

      // End any held meeting (the mini call widget in top-left)
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const endBtn = btns.find(b => b.getAttribute('title')?.toLowerCase().includes('end call'));
        if (endBtn) endBtn.click();
      });
      await sleep(2000);

      // Click Meet again after leaving
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const meetBtn = btns.find(b => b.textContent?.trim() === 'Meet');
        if (meetBtn) meetBtn.click();
      });
      await sleep(2000);
    }

    // Click "Create a meeting link" button
    log('PASS', 'Clicking "Create a meeting link" button');
    const createClicked = await page.evaluate(() => {
      const byTid = document.querySelector('[data-tid="create-meeting-link"]');
      if (byTid) { byTid.click(); return true; }
      const btns = Array.from(document.querySelectorAll('button'));
      const btn = btns.find(b => b.textContent?.trim() === 'Create a meeting link');
      if (btn) { btn.click(); return true; }
      return false;
    });

    if (!createClicked) {
      log('FAIL', 'Could not find "Create a meeting link" button');
      await page.screenshot({ path: '/tmp/teams-create-fail-btn.png' });
      process.exit(1);
    }
    await sleep(2000);

    // Optionally set meeting name in the dialog
    try {
      await page.evaluate((meetingName) => {
        const inputs = Array.from(document.querySelectorAll('input[type=text]'));
        const nameInput = inputs.find(i => i.value && (i.value.includes('Meeting') || i.placeholder?.includes('meeting')));
        if (nameInput) {
          nameInput.value = meetingName;
          nameInput.dispatchEvent(new Event('input', { bubbles: true }));
          nameInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }, name);
    } catch {}

    // Click "Create and copy link"
    log('PASS', 'Clicking "Create and copy link"');
    const copyClicked = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const btn = btns.find(b => b.textContent?.trim() === 'Create and copy link');
      if (btn) { btn.click(); return true; }
      return false;
    });

    if (!copyClicked) {
      log('FAIL', 'Could not find "Create and copy link" button');
      await page.screenshot({ path: '/tmp/teams-create-fail-copy.png' });
      process.exit(1);
    }

    // Wait for API response (up to 10s)
    log('PASS', 'Waiting for meeting creation API response...');
    apiMeetingUrl = await Promise.race([
      responsePromise,
      sleep(10000).then(() => null),
    ]);

    // Fallback 1: read from clipboard (Teams copies the URL there on "Create and copy link")
    if (!apiMeetingUrl) {
      log('DEGRADED', 'API interception timed out, trying clipboard fallback');
      await sleep(1000);
      try {
        const clip = await page.evaluate(async () => {
          try { return await navigator.clipboard.readText(); } catch(e) { return null; }
        });
        if (clip && clip.includes('teams.live.com/meet/')) {
          apiMeetingUrl = clip.trim();
          log('PASS', `Got meeting URL from clipboard: ${apiMeetingUrl}`);
        }
      } catch (e) {
        log('DEGRADED', `Clipboard read failed: ${e.message}`);
      }
    }

    // Fallback 2: scan page DOM for meeting URL
    if (!apiMeetingUrl) {
      log('DEGRADED', 'Trying DOM fallback');
      await sleep(1000);
      apiMeetingUrl = await page.evaluate(() => {
        const links = Array.from(document.querySelectorAll('a[href*="teams.live.com/meet"]'));
        if (links.length > 0) return links[0].href;
        const text = document.body.innerText;
        const match = text.match(/(https:\/\/teams\.live\.com\/meet\/[^\s\n]+)/);
        return match ? match[1] : null;
      });
    }

    if (!apiMeetingUrl) {
      log('FAIL', 'Could not extract meeting URL from API or DOM');
      await page.screenshot({ path: '/tmp/teams-create-fail.png' });
      process.exit(1);
    }

    // Clean up URL
    const meetingUrl = apiMeetingUrl.trim().replace(/[,;.]+$/, '');
    log('PASS', `Meeting link obtained: ${meetingUrl}`);

    // Join as organizer by clicking "Join" on the newly created meeting card.
    // We do NOT navigate to the meeting URL directly — that can create a spurious
    // second meeting if Teams interprets the link as "start new".
    // Instead, click the "Join" button on the card that just appeared ("Created just now").
    log('PASS', 'Joining as organizer via "Join" button on meeting card...');
    try {
      // Wait a moment for the new card to appear in the meeting list
      await sleep(1000);

      const joinClicked = await page.evaluate(() => {
        // Find the "Join" button in the most recently created meeting card
        // The new card should say "Created just now" or be the first in the list
        const btns = Array.from(document.querySelectorAll('button'));
        // Find "Join" buttons that are visible
        const joinBtns = btns.filter(b =>
          b.textContent?.trim() === 'Join' && b.getBoundingClientRect().width > 0
        );
        if (joinBtns.length === 0) return 'no-join-button';
        // Click the first one (newest meeting card at top of list)
        joinBtns[0].click();
        return 'clicked';
      }).catch(() => 'error');

      log('PASS', `Join button click result: ${joinClicked}`);

      if (joinClicked === 'clicked') {
        // After clicking "Join", Teams shows a pre-join screen
        await sleep(5000);

        // Check if we're already in the meeting (direct join without pre-join screen)
        const alreadyIn = await page.evaluate(() => {
          return !!document.querySelector('[data-tid="hangup-main-btn"]');
        }).catch(() => false);

        if (alreadyIn) {
          log('PASS', 'Organizer is IN the meeting room (direct entry) — lobby admission ready');
        } else {
          // Click "Join now" on pre-join screen
          const preJoinState = await page.evaluate(() => {
            const joinBtn = document.querySelector('[data-tid="prejoin-join-button"]');
            if (joinBtn && joinBtn.getBoundingClientRect().width > 0) {
              joinBtn.click();
              return 'clicked-by-tid';
            }
            const btns = Array.from(document.querySelectorAll('button'));
            const btn = btns.find(b => b.textContent?.trim() === 'Join now' && b.getBoundingClientRect().width > 0);
            if (btn) { btn.click(); return 'clicked-by-text'; }
            return 'not-found';
          }).catch(() => 'error');

          log('PASS', `Pre-join click result: ${preJoinState}`);

          if (preJoinState !== 'not-found' && preJoinState !== 'error') {
            // Poll for meeting entry (up to 15s)
            let confirmedInMeeting = false;
            for (let i = 0; i < 5; i++) {
              await sleep(3000);
              confirmedInMeeting = await page.evaluate(() => {
                return !!document.querySelector('[data-tid="hangup-main-btn"]');
              }).catch(() => false);
              if (confirmedInMeeting) break;
            }
            if (confirmedInMeeting) {
              log('PASS', 'Organizer is now IN the meeting room — lobby admission ready');
            } else {
              log('DEGRADED', 'Pre-join button clicked but could not confirm entry into meeting');
              await page.screenshot({ path: '/tmp/teams-join-state.png' }).catch(() => {});
            }
          } else {
            log('DEGRADED', 'Could not find "Join now" button on pre-join screen');
            await page.screenshot({ path: '/tmp/teams-prejoin-state.png' }).catch(() => {});
          }
        }
      } else {
        log('DEGRADED', `Could not click "Join" button: ${joinClicked}`);
        await page.screenshot({ path: '/tmp/teams-join-fallback.png' }).catch(() => {});
      }
    } catch (err) {
      log('DEGRADED', `Could not auto-join as organizer: ${err.message}`);
    }

    // Output meeting URL to stdout (run.js parses the MEETING: line)
    console.log(`MEETING:${meetingUrl}`);

  } catch (err) {
    log('FAIL', `Error creating Teams meeting: ${err.message}\n${err.stack}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  log('FAIL', `Unhandled error: ${err.message}`);
  process.exit(1);
});
