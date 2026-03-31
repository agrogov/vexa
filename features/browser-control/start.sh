#!/bin/bash
set -e

# Clean stale locks from previous runs
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# --- PulseAudio with virtual mic ---
# Start PulseAudio in background (not daemonized — avoids socket issues in containers)
pulseaudio --daemonize=false --exit-idle-time=-1 --disallow-exit &
# Wait for PulseAudio socket to be ready
for i in $(seq 1 20); do
    if pactl info >/dev/null 2>&1; then break; fi
    sleep 0.2
done
# Load virtual mic sink and set it as default source (mic input)
pactl load-module module-null-sink sink_name=virtual_mic sink_properties=device.description=VirtualMic || true
pactl set-default-source virtual_mic.monitor || true
pactl set-default-sink virtual_mic || true
echo "PulseAudio started with virtual_mic sink"

# --- Xvfb ---
Xvfb :99 -screen 0 1920x1080x24 &
sleep 1

# --- Fluxbox (maximize windows) ---
mkdir -p /root/.fluxbox
cat > /root/.fluxbox/apps <<'FBAPPS'
[app] (name=.*) (class=.*)
  [Maximized]  {yes}
[end]
FBAPPS
fluxbox &

# --- VNC ---
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 &

# --- noVNC (web-based VNC on port 6080) ---
websockify --web /usr/share/novnc 6080 localhost:5900 &

# --- Chromium via Playwright with CDP ---
mkdir -p /app/userdata
rm -f /app/userdata/SingletonLock /app/userdata/SingletonCookie /app/userdata/SingletonSocket
cd /app && node -e "
const { chromium } = require('playwright');
(async () => {
  const context = await chromium.launchPersistentContext('/app/userdata', {
    headless: false,
    ignoreDefaultArgs: ['--enable-automation'],
    args: [
      '--remote-debugging-port=9222',
      '--remote-debugging-address=0.0.0.0',
      '--disable-blink-features=AutomationControlled',
      '--start-maximized',
      '--use-fake-ui-for-media-stream',
      '--autoplay-policy=no-user-gesture-required'
    ],
    viewport: null
  });
  const page = context.pages()[0] || await context.newPage();
  await page.goto('about:blank');
  console.log('Browser ready. CDP at http://localhost:9222');
  await new Promise(() => {});
})();
" &

# Wait for CDP to be ready, then proxy it on 0.0.0.0:9223
(while ! curl -s http://localhost:9222/json/version > /dev/null 2>&1; do sleep 1; done
echo "CDP ready, starting socat proxy on 0.0.0.0:9223"
socat TCP-LISTEN:9223,fork,reuseaddr,bind=0.0.0.0 TCP:localhost:9222) &

echo "All services started (Xvfb, Fluxbox, VNC, noVNC, PulseAudio, Chromium+CDP)"
wait
