import { chromium } from 'playwright-extra';
import { createClient, RedisClientType } from 'redis';
import { execSync } from 'child_process';
import { mkdirSync, existsSync, unlinkSync } from 'fs';
import { join } from 'path';
import { getBrowserSessionArgs } from './constans';
import { BrowserSessionConfig } from './types';

const BROWSER_DATA_DIR = '/tmp/browser-data';
const WORKSPACE_DIR = '/workspace';

// --- S3 sync helpers ---

function getS3Env(config: BrowserSessionConfig): Record<string, string> {
  return {
    ...process.env as Record<string, string>,
    AWS_ACCESS_KEY_ID: config.s3AccessKey || '',
    AWS_SECRET_ACCESS_KEY: config.s3SecretKey || '',
  };
}

function s3Sync(localDir: string, s3Path: string, config: BrowserSessionConfig, direction: 'up' | 'down', excludes: string[] = []): void {
  if (!config.userdataS3Path || !config.s3Endpoint || !config.s3Bucket) return;
  const s3Uri = `s3://${config.s3Bucket}/${s3Path}`;
  const excludeArgs = excludes.map(e => `--exclude "${e}"`).join(' ');
  const deleteArg = direction === 'up' ? '--delete' : '';
  const [src, dst] = direction === 'down' ? [s3Uri, `${localDir}/`] : [`${localDir}/`, s3Uri];
  console.log(`[browser-session] S3 sync ${direction}: ${src} → ${dst}`);
  try {
    execSync(
      `aws s3 sync "${src}" "${dst}" --endpoint-url "${config.s3Endpoint}" ${deleteArg} ${excludeArgs}`,
      { env: getS3Env(config), stdio: 'inherit', timeout: 120000 }
    );
  } catch (err: any) {
    console.log(`[browser-session] S3 sync ${direction} issue: ${err.message}`);
  }
}

// --- Git workspace helpers ---

function gitRepoUrl(config: BrowserSessionConfig): string {
  const repo = config.workspaceGitRepo!;
  const token = config.workspaceGitToken;
  if (!token) return repo;
  // Inject token into HTTPS URL: https://TOKEN@github.com/user/repo.git
  return repo.replace('https://', `https://${token}@`);
}

function syncWorkspaceFromGit(config: BrowserSessionConfig): void {
  const branch = config.workspaceGitBranch || 'main';
  const url = gitRepoUrl(config);
  console.log(`[browser-session] Git clone workspace from ${config.workspaceGitRepo} (${branch})`);
  try {
    if (existsSync(join(WORKSPACE_DIR, '.git'))) {
      // Already cloned — pull latest (ignore errors if remote branch doesn't exist yet)
      try {
        execSync(`git fetch origin && git reset --hard origin/${branch}`, { cwd: WORKSPACE_DIR, stdio: 'pipe', timeout: 60000 });
        console.log('[browser-session] Git pull complete');
      } catch {
        console.log('[browser-session] Git pull skipped (remote branch may not exist yet)');
      }
    } else {
      // Fresh clone — try with branch, fall back to bare clone, fall back to init
      try {
        execSync(`git clone --branch ${branch} "${url}" ${WORKSPACE_DIR}`, { stdio: 'pipe', timeout: 120000 });
      } catch {
        // Repo might be empty — clone without branch
        try {
          execSync(`git clone "${url}" ${WORKSPACE_DIR}`, { stdio: 'pipe', timeout: 120000 });
        } catch {
          // Truly empty repo or auth issue — init locally and set remote
          execSync('git init', { cwd: WORKSPACE_DIR, stdio: 'pipe' });
          execSync(`git remote add origin "${url}"`, { cwd: WORKSPACE_DIR, stdio: 'pipe' });
          console.log('[browser-session] Initialized empty workspace with remote');
        }
      }
      execSync('git config user.email "bot@vexa.ai"', { cwd: WORKSPACE_DIR, stdio: 'pipe' });
      execSync('git config user.name "Vexa Bot"', { cwd: WORKSPACE_DIR, stdio: 'pipe' });
      console.log('[browser-session] Git clone complete');
    }
  } catch (err: any) {
    console.log(`[browser-session] Git clone/pull failed: ${err.message}`);
  }
}

function syncWorkspaceToGit(config: BrowserSessionConfig): void {
  const branch = config.workspaceGitBranch || 'main';
  console.log(`[browser-session] Git push workspace to ${config.workspaceGitRepo}`);
  try {
    execSync('git add -A', { cwd: WORKSPACE_DIR, stdio: 'pipe' });
    const status = execSync('git status --porcelain', { cwd: WORKSPACE_DIR, encoding: 'utf8' }).trim();
    if (status) {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      execSync(`git commit -m "save ${timestamp}"`, { cwd: WORKSPACE_DIR, stdio: 'pipe' });
    }
    execSync(`git push origin ${branch}`, { cwd: WORKSPACE_DIR, stdio: 'pipe', timeout: 60000 });
    console.log('[browser-session] Git push complete');
  } catch (err: any) {
    console.log(`[browser-session] Git push failed: ${err.message}`);
  }
}

function useGitWorkspace(config: BrowserSessionConfig): boolean {
  return !!(config.workspaceGitRepo);
}

// --- Workspace sync (git or S3) ---

function syncWorkspaceDown(config: BrowserSessionConfig): void {
  if (useGitWorkspace(config)) {
    syncWorkspaceFromGit(config);
  } else {
    s3Sync(WORKSPACE_DIR, `${config.userdataS3Path}/workspace`, config, 'down');
  }
}

function syncWorkspaceUp(config: BrowserSessionConfig): void {
  if (useGitWorkspace(config)) {
    syncWorkspaceToGit(config);
  } else {
    s3Sync(WORKSPACE_DIR, `${config.userdataS3Path}/workspace`, config, 'up');
  }
}

function syncBrowserDataFromS3(config: BrowserSessionConfig): void {
  s3Sync(BROWSER_DATA_DIR, `${config.userdataS3Path}/browser-data`, config, 'down');
}

function syncBrowserDataToS3(config: BrowserSessionConfig): void {
  // Exclude Chromium cache and temp files that are large and transient
  const excludes = [
    'Cache/*', 'Code Cache/*', 'GrShaderCache/*', 'ShaderCache/*', 'GraphiteDawnCache/*',
    'Service Worker/CacheStorage/*', 'BrowserMetrics*', '*-journal',
    'SingletonLock', 'SingletonCookie', 'SingletonSocket',
  ];
  s3Sync(BROWSER_DATA_DIR, `${config.userdataS3Path}/browser-data`, config, 'up', excludes);
}

function saveAll(config: BrowserSessionConfig): void {
  console.log('[browser-session] Saving workspace...');
  syncWorkspaceUp(config);
  console.log('[browser-session] Saving browser data...');
  syncBrowserDataToS3(config);
  console.log('[browser-session] Save complete');
}

// --- Clean stale Chromium lock files ---

function cleanStaleLocks(): void {
  const lockFiles = ['SingletonLock', 'SingletonCookie', 'SingletonSocket'];
  for (const f of lockFiles) {
    const p = join(BROWSER_DATA_DIR, f);
    if (existsSync(p)) {
      try { unlinkSync(p); } catch {}
      console.log(`[browser-session] Removed stale lock: ${f}`);
    }
  }
}

// --- Main entry point ---

export async function runBrowserSession(config: BrowserSessionConfig): Promise<void> {
  // Create directories
  mkdirSync(BROWSER_DATA_DIR, { recursive: true });
  mkdirSync(WORKSPACE_DIR, { recursive: true });

  // Download existing data
  syncBrowserDataFromS3(config);
  syncWorkspaceDown(config);

  // Clean stale locks
  cleanStaleLocks();

  // Launch persistent browser context
  const context = await chromium.launchPersistentContext(BROWSER_DATA_DIR, {
    headless: false,
    ignoreDefaultArgs: ['--enable-automation'],
    args: getBrowserSessionArgs(),
    viewport: null,
  });

  // Get or create a page
  const pages = context.pages();
  const page = pages.length > 0 ? pages[0] : await context.newPage();
  await page.goto('about:blank');

  console.log('[browser-session] Browser session ready. VNC :6080, CDP :9222');
  console.log(`[browser-session] Workspace: ${WORKSPACE_DIR}`);
  console.log(`[browser-session] Browser data: ${BROWSER_DATA_DIR}`);

  // Set up Redis subscriber for commands
  const channelName = `browser_session:${config.container_name || 'default'}`;

  if (config.redisUrl) {
    const subscriber: RedisClientType = createClient({ url: config.redisUrl }) as RedisClientType;
    const publisher: RedisClientType = createClient({ url: config.redisUrl }) as RedisClientType;
    await subscriber.connect();
    await publisher.connect();

    await subscriber.subscribe(channelName, async (message: string) => {
      console.log(`[browser-session] Redis command: ${message}`);

      if (message === 'save_storage') {
        saveAll(config);
        await publisher.publish(channelName, 'save_storage:done');
      } else if (message === 'stop') {
        console.log('[browser-session] Stop command received, saving and exiting...');
        saveAll(config);
        await context.close();
        process.exit(0);
      }
    });

    console.log(`[browser-session] Listening for commands on Redis channel: ${channelName}`);
  }

  // Graceful shutdown
  const shutdown = async () => {
    console.log('[browser-session] Shutting down, saving...');
    saveAll(config);
    await context.close();
    process.exit(0);
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  // Keep alive
  await new Promise(() => {});
}
