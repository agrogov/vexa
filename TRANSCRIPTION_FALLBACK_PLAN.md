# Transcription Service Fallback Plan

When the in-cluster `transcription-service` stops responding, bots should automatically switch to an externally deployed transcription service for the remainder of the session.

## Approach

Bot-level fallback inside `TranscriptionClient`. The bot already retries on 503/429; after retries are exhausted it switches to a secondary URL+token and continues the session. This handles mid-session failures — a k8s-level check at pod launch time would not.

## Files to Change

### 1. `services/vexa-bot/core/src/types.ts`

Extend `BotConfig` with two optional fields:

```ts
transcriptionServiceFallbackUrl?: string
transcriptionServiceFallbackToken?: string
```

### 2. `services/vexa-bot/core/src/services/transcription-client.ts`

After the retry loop exhausts all attempts, if `fallbackUrl` is configured:
- Log a warning: _"primary transcription service unreachable, switching to fallback"_
- Swap `activeUrl` / `activeToken` to fallback values
- Reset retry counter and re-attempt
- Once on fallback, do not switch back (session-scoped, one-way)

Trigger condition: connection refused, timeout, or repeated 5xx — **not** a single transient 503.

~15–20 lines, entirely within the existing error-handling path.

### 3. `services/bot-manager/app/orchestrators/kubernetes.py`

Read two new env vars and inject them into the `BOT_CONFIG` JSON blob:

```
TRANSCRIPTION_SERVICE_FALLBACK_URL
TRANSCRIPTION_SERVICE_FALLBACK_TOKEN
```

Mirror the existing pattern for `transcriptionServiceUrl` / `transcriptionServiceToken`. Apply the same to `docker.py` and `process.py` if those orchestrators are in use.

### 4. `helm/charts/vexa/templates/deployment-bot-manager.yaml`

Expose the two new env vars on the bot-manager Pod, using the same three-option chain already built for the primary token:
1. Plain value (`transcriptionServiceFallbackToken`)
2. Secret reference with configurable key name (`transcriptionServiceFallbackSecretName` + `transcriptionServiceFallbackTokenSecretKey`)
3. Fall through to chart-managed secret

### 5. `helm/charts/vexa/values.yaml`

```yaml
botManager:
  # Fallback transcription service — used when the primary is unreachable.
  # URL: leave empty to disable fallback entirely.
  transcriptionServiceFallbackUrl: ""
  transcriptionServiceFallbackSecretName: ""       # defaults to secrets.existingSecretName when blank
  transcriptionServiceFallbackTokenSecretKey: "TRANSCRIBER_API_KEY"
```

## What Does Not Change

- `transcription-service` — no server-side changes
- Bot-manager API or database models
- Helm templates for any other service
- Kubernetes Service / networking layer

## Estimated Scope

4–5 files, ~50–70 lines net.

## Example Cluster Values Override

```yaml
botManager:
  transcriptionServiceUrl: "http://infobip-vexa-transcription-service.vexa.svc.cluster.local:8000/v1/audio/transcriptions"
  transcriptionServiceTokenSecretKey: "TRANSCRIBER_API_KEY"

  transcriptionServiceFallbackUrl: "http://p5-se1-emorc-2.ancotel.local:8000/v1/audio/transcriptions"
  transcriptionServiceFallbackSecretName: "vexa-secrets"
  transcriptionServiceFallbackTokenSecretKey: "GPU_TRANSCRIBER_API_KEY"
```
