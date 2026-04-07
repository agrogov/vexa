# bot-manager changes

## main.py — always delete bot pod on exit
- `bot_exit_callback`: removed `exit_code != 0` guard on pod cleanup — completed pods (`exit_code=0`) were never deleted, accumulating as `Completed` in K8s indefinitely
- Pod deletion is now scheduled via `_delayed_container_stop` on every exit callback regardless of success or failure

## orchestrator_utils.py — wire Teams timing config into BOT_CONFIG
- Added `teamsSignalLossGraceMs` and `teamsSpeakingKeepaliveMs` to `bot_config_data`
- Values read from `TEAMS_SIGNAL_LOSS_GRACE_MS` / `TEAMS_SPEAKING_KEEPALIVE_MS` env vars (defaults: 2000ms / 8000ms)
- These env vars are already set in the Helm chart's bot-manager extraEnv; without this change they were never passed to the bot

## orchestrators/kubernetes.py — browser session pod support + extra_bot_config
- Added `start_browser_session_container()`: spawns a vexa-bot Pod in `browser_session` mode with VNC (6080) and CDP (9223) ports exposed; used for interactive/debug bot sessions
- Added `extra_bot_config` parameter to `start_bot_container()` so callers can inject additional fields into `BOT_CONFIG` JSON without modifying the base config builder
- Exported `start_browser_session_container` in `__all__`
