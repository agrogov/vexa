import { Page } from "playwright";
import { log } from "../../utils";

/**
 * Enable Teams live captions for the bot's browser session.
 *
 * Captions are per-user — the bot can always enable them for itself
 * regardless of meeting settings. Once enabled, the caption DOM elements
 * (data-tid="author" + data-tid="closed-caption-text") appear in the page
 * and are observed by the caption MutationObserver in recording.ts.
 *
 * Flow: More → Language and speech → Show live captions
 */
export async function enableTeamsLiveCaptions(page: Page): Promise<void> {
  log("[Captions] Attempting to enable Teams live captions...");

  // Wait for the meeting UI to stabilize
  await page.waitForTimeout(3000);

  // Check if captions are already enabled
  const alreadyEnabled = await page.evaluate(() => {
    return !!document.querySelector('[data-tid="closed-caption-renderer-wrapper"]');
  });

  if (alreadyEnabled) {
    log("[Captions] Live captions already enabled");
    return;
  }

  try {
    // Step 1: Click "More" button in the meeting toolbar.
    // Use JS click first to bypass the ui-dialog__overlay that intercepts pointer
    // events in the Teams light experience (same pattern as leave.ts).
    const jsMoreResult = await page.evaluate(() => {
      const overlays = document.querySelectorAll<HTMLElement>('.ui-dialog__overlay, [data-slot-name\\:rj\\:="root"].ui-box');
      const overlayCount = overlays.length;
      for (const ov of overlays) {
        ov.style.pointerEvents = 'none';
      }
      const btn =
        document.getElementById('callingButtons-showMoreBtn') ||
        document.querySelector<HTMLElement>('button[aria-label="More"]') ||
        document.querySelector<HTMLElement>('button[aria-label="More options"]');
      if (btn) {
        const rect = btn.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          btn.click();
          return { clicked: true, overlayCount };
        }
      }
      return { clicked: false, overlayCount };
    });

    if (jsMoreResult.overlayCount > 0) {
      log(`[Captions] ⚠️ Detected ${jsMoreResult.overlayCount} blocking overlay(s) (Teams light experience) — neutralized pointer-events`);
    }

    if (jsMoreResult.clicked) {
      log("[Captions] Clicked More menu (JS click)");
    } else {
      // Fallback: Playwright force-click
      const moreButton = page.locator(
        '#callingButtons-showMoreBtn, button[aria-label="More"], button[aria-label="More options"]'
      ).first();
      await moreButton.click({ force: true, timeout: 8000 });
      log("[Captions] Clicked More menu (force-click fallback)");
    }
    await page.waitForTimeout(1000);

    // Step 2: Click "Language and speech" — use broad text matching.
    // Log visible menu items for diagnostics.
    const menuItems = await page.evaluate(() => {
      const items = document.querySelectorAll('[role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"]');
      return Array.from(items).map(el => ({
        text: (el.textContent || '').trim().substring(0, 60),
        role: el.getAttribute('role') || '',
        visible: (el as HTMLElement).offsetParent !== null
      })).filter(i => i.visible);
    });
    log(`[Captions] Menu items: ${menuItems.map(i => i.text).join(' | ')}`);

    // Step 2: Enable captions.
    // Guest menu has "Captions" directly (no "Language and speech" submenu).
    // Host menu has "Language and speech" → "Show live captions" submenu.
    // Try both paths.
    const enableResult = await page.evaluate(() => {
      const getVisibleItems = () => {
        const items = document.querySelectorAll('[role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"]');
        return Array.from(items).filter(el => (el as HTMLElement).offsetParent !== null);
      };

      const items = getVisibleItems();
      const texts = items.map(el => (el.textContent || '').trim().toLowerCase());

      // Path A (guest): Direct "Captions" menu item
      for (const el of items) {
        const text = (el.textContent || '').trim().toLowerCase();
        if (text === 'captions' || text === 'show live captions' || text === 'turn on live captions') {
          (el as HTMLElement).click();
          return { clicked: (el.textContent || '').trim(), path: 'direct' };
        }
      }

      // Path B (host): "Language and speech" submenu
      for (const el of items) {
        const text = (el.textContent || '').toLowerCase();
        if (text.includes('language') && text.includes('speech')) {
          (el as HTMLElement).click();
          return { clicked: (el.textContent || '').trim(), path: 'submenu' };
        }
      }

      return { clicked: null, path: 'none', available: texts.join(' | ') };
    });

    if (!enableResult.clicked) {
      throw new Error(`Could not find captions menu item. Available: ${(enableResult as any).available}`);
    }

    log(`[Captions] Clicked: "${enableResult.clicked}" (${enableResult.path})`);
    await page.waitForTimeout(1000);

    // If we went through submenu path, need to click the actual captions toggle
    if (enableResult.path === 'submenu') {
      const clickedSub = await page.evaluate(() => {
        const items = document.querySelectorAll('[role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"]');
        for (const el of items) {
          const text = (el.textContent || '').toLowerCase();
          if (text.includes('live captions') && (el as HTMLElement).offsetParent) {
            (el as HTMLElement).click();
            return (el.textContent || '').trim();
          }
        }
        return null;
      });
      if (clickedSub) {
        log(`[Captions] Clicked submenu: "${clickedSub}"`);
      } else {
        log("[Captions] ⚠️ Could not find live captions in submenu");
      }
      await page.waitForTimeout(1500);
    }

    // Verify captions are now enabled (poll for up to 5s — wrapper may appear with delay)
    let captionsEnabled = false;
    for (let attempt = 0; attempt < 10; attempt++) {
      captionsEnabled = await page.evaluate(() => {
        return !!document.querySelector('[data-tid="closed-caption-renderer-wrapper"]');
      });
      if (captionsEnabled) break;
      await page.waitForTimeout(500);
    }

    if (captionsEnabled) {
      log("[Captions] ✅ Live captions enabled successfully — caption-driven transcription pipeline active");
    } else {
      log("[Captions] ❌ Live captions could NOT be enabled — caption wrapper not found after menu interaction. Transcription will rely on DOM speaker signals (degraded quality).");
    }
  } catch (err: any) {
    // Close any open menu before re-throwing
    try {
      await page.keyboard.press('Escape');
    } catch {}
    log(`[Captions] ❌ Caption enablement failed: ${err?.message || err}`);
    throw err;
  }
}
