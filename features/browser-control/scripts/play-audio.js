#!/usr/bin/env node
// Play a WAV file through PulseAudio virtual mic in a Docker container.
// Usage: node play-audio.js <wav-file> [--container vexa-host] [--device virtual_mic]
//
// When run inside the container: uses paplay directly.
// When run outside: uses docker exec to run paplay in the container.
//
// Outputs: PLAYING:<file> and DONE:<file>
// Exits 0 on success, 1 on failure.

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const LOG_FILE = '/home/dima/dev/vexa/test.log';
const AGENT = 'browser-control/play-audio';

function log(level, msg) {
  const line = `[${new Date().toISOString()}] [${AGENT}] ${level}: ${msg}`;
  console.error(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function parseArgs() {
  const args = process.argv.slice(2);
  let wavFile = null;
  let container = process.env.CONTAINER_NAME || 'vexa-host';
  let device = process.env.PULSE_DEVICE || 'virtual_mic';
  let inside = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--container' && args[i + 1]) { container = args[++i]; continue; }
    if (args[i] === '--device' && args[i + 1]) { device = args[++i]; continue; }
    if (args[i] === '--inside') { inside = true; continue; }
    if (!wavFile) wavFile = args[i];
  }

  // Auto-detect if running inside a container
  if (!inside) {
    try {
      inside = fs.existsSync('/.dockerenv') || fs.readFileSync('/proc/1/cgroup', 'utf8').includes('docker');
    } catch {
      inside = false;
    }
  }

  return { wavFile, container, device, inside };
}

function playInside(wavFile, device) {
  return new Promise((resolve, reject) => {
    const absPath = path.resolve(wavFile);
    if (!fs.existsSync(absPath)) {
      reject(new Error(`File not found: ${absPath}`));
      return;
    }

    log('PASS', `Playing ${absPath} on device ${device} (inside container)`);
    console.log(`PLAYING:${absPath}`);

    const proc = spawn('paplay', ['--device=' + device, absPath], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stderr = '';
    proc.stderr.on('data', d => { stderr += d.toString(); });

    proc.on('close', code => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`paplay exited ${code}: ${stderr.trim()}`));
      }
    });

    proc.on('error', reject);
  });
}

function playOutside(wavFile, container, device) {
  return new Promise((resolve, reject) => {
    // Resolve to absolute path on host
    const absPath = path.resolve(wavFile);
    if (!fs.existsSync(absPath)) {
      reject(new Error(`File not found: ${absPath}`));
      return;
    }

    // Check if the file is already accessible inside the container at the same path
    // or we need to docker cp it first
    const containerPath = `/tmp/${path.basename(absPath)}`;

    log('PASS', `Copying ${absPath} to ${container}:${containerPath}`);
    try {
      execSync(`docker cp "${absPath}" "${container}:${containerPath}"`, { timeout: 30000 });
    } catch (err) {
      reject(new Error(`docker cp failed: ${err.message}`));
      return;
    }

    log('PASS', `Playing ${containerPath} on device ${device} via docker exec`);
    console.log(`PLAYING:${absPath}`);

    const proc = spawn('docker', ['exec', container, 'paplay', `--device=${device}`, containerPath], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stderr = '';
    proc.stderr.on('data', d => { stderr += d.toString(); });

    proc.on('close', code => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`docker exec paplay exited ${code}: ${stderr.trim()}`));
      }
    });

    proc.on('error', reject);
  });
}

async function main() {
  const { wavFile, container, device, inside } = parseArgs();

  if (!wavFile) {
    console.error('Usage: node play-audio.js <wav-file> [--container name] [--device name] [--inside]');
    process.exit(1);
  }

  try {
    if (inside) {
      await playInside(wavFile, device);
    } else {
      await playOutside(wavFile, container, device);
    }

    log('PASS', `Finished playing ${wavFile}`);
    console.log(`DONE:${wavFile}`);
  } catch (err) {
    log('FAIL', `Error playing audio: ${err.message}`);
    process.exit(1);
  }
}

main().catch(err => {
  log('FAIL', `Unhandled error: ${err.message}`);
  process.exit(1);
});
