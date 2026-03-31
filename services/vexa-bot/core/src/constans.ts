// User Agent for consistency - Updated to modern Chrome version for Google Meet compatibility
export const userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36";

// Base browser launch arguments (shared across all modes)
const baseBrowserArgs = [
  "--incognito",
  "--no-sandbox",
  "--disable-setuid-sandbox",
  "--disable-features=IsolateOrigins,site-per-process",
  "--disable-infobars",
  "--disable-gpu",
  "--use-fake-ui-for-media-stream",
  "--use-file-for-fake-video-capture=/dev/null",
  "--allow-running-insecure-content",
  "--disable-web-security",
  "--disable-features=VizDisplayCompositor",
  "--ignore-certificate-errors",
  "--ignore-ssl-errors",
  "--ignore-certificate-errors-spki-list",
  "--disable-site-isolation-trials"
];

/**
 * Get browser launch arguments based on capability flags.
 *
 * PulseAudio (real audio device) is needed when:
 *   - ttsEnabled: bot speaks via TTS
 *   - voiceAgentEnabled (deprecated): alias for ttsEnabled
 *   - cameraEnabled: virtual camera may need audio sync
 *
 * Otherwise: --use-file-for-fake-audio-capture=/dev/null → silence as mic input
 *
 * Video capture is always /dev/null from base args. Camera init script handles
 * virtual camera separately when cameraEnabled is true.
 */
export function getBrowserArgs(needsAudio: boolean = false): string[] {
  let args = [...baseBrowserArgs];
  if (!needsAudio) {
    // Pure listener — /dev/null, truly silent, no PulseAudio
    args.push("--use-file-for-fake-audio-capture=/dev/null");
  }
  // If needsAudio: PulseAudio with muted tts_sink (entrypoint.sh)
  return args;
}

// Default browser args for backward compatibility (voice agent disabled)
export const browserArgs = getBrowserArgs(false);

/**
 * Browser args for interactive browser session mode (VNC + CDP).
 * No incognito, no fake media — human interacts via VNC, agent via CDP.
 */
export function getBrowserSessionArgs(): string[] {
  return [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-blink-features=AutomationControlled',
    '--start-maximized',
    '--remote-debugging-port=9222',
    '--remote-debugging-address=0.0.0.0',
    '--remote-allow-origins=*',
  ];
}
