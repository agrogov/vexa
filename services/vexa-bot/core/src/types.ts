export type BotConfig = {
  platform: "google_meet" | "zoom" | "teams",
  meetingUrl: string | null,
  botName: string,
  token: string,  // MeetingToken (HS256 JWT)
  obfToken?: string,
  connectionId: string,
  nativeMeetingId: string,
  language?: string | null,
  task?: string | null,
  transcribeEnabled?: boolean,
  transcriptionTier?: "realtime" | "deferred",
  redisUrl: string,
  container_name?: string,
  automaticLeave: {
    waitingRoomTimeout: number,
    noOneJoinedTimeout: number,
    everyoneLeftTimeout: number
  },
  reconnectionIntervalMs?: number,
  meeting_id: number,  // Required, not optional
  botManagerCallbackUrl?: string;
  recordingEnabled?: boolean;
  captureModes?: string[];  // e.g., ['audio'], ['audio', 'video'], ['audio', 'screenshots']
  recordingUploadUrl?: string;  // bot-manager internal upload endpoint

  // Per-speaker transcription
  transcriptionServiceUrl?: string;   // HTTP endpoint for transcription-service
  transcriptionServiceToken?: string; // Bearer token for transcription-service

  // Voice agent / meeting interaction interface
  voiceAgentEnabled?: boolean;  // DEPRECATED: treat as alias for ttsEnabled. No camera.
  ttsEnabled?: boolean;        // Enable TTS: PulseAudio gain=0 idle, gain=1 during /speak
  defaultAvatarUrl?: string;   // Custom default avatar image URL for virtual camera

  // Independent capability flags
  videoReceiveEnabled?: boolean;  // Receive+decode video from participants (default: false)
  cameraEnabled?: boolean;        // Outgoing virtual camera/avatar (default: false)

  // Authenticated meeting mode (uses persistent browser context with stored userdata)
  authenticated?: boolean;
  userdataS3Path?: string;   // e.g. "users/123/browser-userdata"
  s3Endpoint?: string;
  s3Bucket?: string;
  s3AccessKey?: string;
  s3SecretKey?: string;
}

export type BrowserSessionConfig = {
  mode: "browser_session";
  redisUrl: string;
  container_name?: string;
  botManagerCallbackUrl?: string;
  s3Endpoint?: string;
  s3Bucket?: string;
  s3AccessKey?: string;
  s3SecretKey?: string;
  userdataS3Path?: string; // e.g. "users/123/browser-userdata"
  // Git-based workspace (optional — if set, workspace syncs via git instead of S3)
  workspaceGitRepo?: string;  // e.g. "https://github.com/user/bot-workspace.git"
  workspaceGitToken?: string; // PAT for private repos
  workspaceGitBranch?: string; // default: "main"
}
