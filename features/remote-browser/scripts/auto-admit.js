const { chromium } = require('playwright');
const CDP_URL = process.argv[2] || 'http://localhost:9222';
const POLL_INTERVAL = 3000;

async function tryAdmit(page) {
  return await page.evaluate(() => {
    // Step 1: If confirmation dialog is open, click OK
    const dialogOk = document.querySelector('button[data-mdc-dialog-action="ok"]');
    if (dialogOk && dialogOk.offsetParent) {
      dialogOk.click();
      return 'dialog_confirmed';
    }

    // Step 2: Click individual "Admit" buttons next to person names (no dialog needed)
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      if (btn.textContent.trim() === 'Admit' && btn.offsetParent) {
        btn.click();
        return 'admitted';
      }
    }

    // Step 3: Green pill visible? Click to open People panel so Admit buttons appear
    const roleButtons = document.querySelectorAll('div[role="button"]');
    for (const el of roleButtons) {
      if (/Admit \d+ guest/.test(el.textContent || '') && el.offsetParent) {
        el.click();
        return 'pill_clicked';
      }
    }

    return 'none';
  }).catch(() => 'error');
}

async function main() {
  console.log('Connecting to ' + CDP_URL);
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  const ctx = browser.contexts()[0];
  let page = ctx.pages().find(p => p.url().includes('meet.google.com'));
  if (!page) { console.error('No Meet page'); process.exit(1); }
  console.log('Meeting: ' + page.url());
  console.log('Auto-admit running every ' + (POLL_INTERVAL / 1000) + 's');
  let total = 0;

  process.on('SIGTERM', async () => { await browser.close(); process.exit(0); });
  process.on('SIGINT', async () => { await browser.close(); process.exit(0); });

  while (true) {
    try {
      const r = await tryAdmit(page);
      if (r === 'admitted' || r === 'dialog_confirmed') {
        total++;
        console.log(new Date().toLocaleTimeString() + ' ' + r + ' (' + total + ')');
        await new Promise(resolve => setTimeout(resolve, 1500));
        continue;
      } else if (r === 'pill_clicked') {
        // Panel opening, loop back quickly to find Admit buttons
        await new Promise(resolve => setTimeout(resolve, 800));
        continue;
      }
    } catch (e) {
      if (e.message && (e.message.includes('destroyed') || e.message.includes('closed'))) {
        page = ctx.pages().find(p => p.url().includes('meet.google.com'));
        if (!page) { console.log('Meeting page lost.'); break; }
      }
    }
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
  }
  await browser.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
