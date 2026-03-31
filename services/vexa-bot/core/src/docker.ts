import { runBot } from "."
import { z } from 'zod';
import { BotConfig, BrowserSessionConfig } from "./types"; // Import the BotConfig type

// Define a schema that matches your JSON configuration
export const BotConfigSchema = z.object({
  mode: z.enum(["meeting", "browser_session"]).default("meeting"),
  platform: z.enum(["google_meet", "zoom", "teams"]).optional(),
  meetingUrl: z.string().url().nullable().optional(), // Allow null from BOT_CONFIG
  botName: z.string().optional(),
  token: z.string().optional(),
  connectionId: z.string().optional(),
  nativeMeetingId: z.string().optional(), // *** ADDED schema field ***
  language: z.string().nullish(), // Optional language
  task: z.string().nullish(),     // Optional task
  transcribeEnabled: z.boolean().optional(),
  transcriptionTier: z.enum(["realtime", "deferred"]).optional(),
  redisUrl: z.string(),         // Required Redis URL
  container_name: z.string().optional(), // ADDED: Optional container name
  automaticLeave: z.object({
    waitingRoomTimeout: z.number().int().default(300000),      // 5 minutes
    noOneJoinedTimeout: z.number().int().default(600000),      // 10 minutes
    everyoneLeftTimeout: z.number().int().default(120000)      // 2 minutes
  }).default({}),
  reconnectionIntervalMs: z.number().int().optional(), // ADDED: Optional reconnection interval
  meeting_id: z.number().int().optional(), // Allow optional internal ID
  botManagerCallbackUrl: z.string().url().optional(), // ADDED: Optional callback URL
  recordingEnabled: z.boolean().optional(),
  captureModes: z.array(z.string()).optional(),
  recordingUploadUrl: z.string().url().optional(),
  // Per-speaker transcription
  transcriptionServiceUrl: z.string().optional(),
  transcriptionServiceToken: z.string().optional(),
  // Voice agent / meeting interaction interface
  voiceAgentEnabled: z.boolean().optional(),
  ttsEnabled: z.boolean().optional(),
  defaultAvatarUrl: z.string().url().optional(),
  // Independent capability flags
  videoReceiveEnabled: z.boolean().optional(),
  cameraEnabled: z.boolean().optional(),
  // Authenticated meeting mode / browser session S3 config
  authenticated: z.boolean().optional(),
  userdataS3Path: z.string().optional(),
  s3Endpoint: z.string().optional(),
  s3Bucket: z.string().optional(),
  s3AccessKey: z.string().optional(),
  s3SecretKey: z.string().optional(),
  // Git-based workspace
  workspaceGitRepo: z.string().optional(),
  workspaceGitToken: z.string().optional(),
  workspaceGitBranch: z.string().optional(),
});


(function main() {
const rawConfig = process.env.BOT_CONFIG;
if (!rawConfig) {
  console.error("BOT_CONFIG environment variable is not set");
  process.exit(1);
}

  try {
  // Parse the JSON string from the environment variable
  const parsedConfig = JSON.parse(rawConfig);
  // Validate and parse the config using zod
  const validatedConfig = BotConfigSchema.parse(parsedConfig);

  if (validatedConfig.mode === "browser_session") {
    // Browser session mode — interactive browser with VNC + CDP
    const sessionConfig: BrowserSessionConfig = {
      mode: "browser_session",
      redisUrl: validatedConfig.redisUrl,
      container_name: validatedConfig.container_name,
      botManagerCallbackUrl: validatedConfig.botManagerCallbackUrl,
      s3Endpoint: validatedConfig.s3Endpoint,
      s3Bucket: validatedConfig.s3Bucket,
      s3AccessKey: validatedConfig.s3AccessKey,
      s3SecretKey: validatedConfig.s3SecretKey,
      userdataS3Path: validatedConfig.userdataS3Path,
      workspaceGitRepo: validatedConfig.workspaceGitRepo,
      workspaceGitToken: validatedConfig.workspaceGitToken,
      workspaceGitBranch: validatedConfig.workspaceGitBranch,
    };
    import('./browser-session').then(({ runBrowserSession }) => {
      runBrowserSession(sessionConfig).catch((error) => {
        console.error("Error running browser session:", error);
        process.exit(1);
      });
    });
  } else {
    // Meeting mode — validate required meeting fields and run bot
    const botConfig: BotConfig = validatedConfig as BotConfig;
    runBot(botConfig).catch((error) => {
      console.error("Error running bot:", error);
      process.exit(1);
    });
  }
} catch (error) {
  console.error("Invalid BOT_CONFIG:", error);
  process.exit(1);
}
})()
