# fix(bot-manager): auto-cleanup completed/failed pods and fix image pull policy env var

## Commit title
`fix(bot-manager): schedule pod cleanup on meeting completion/failure, rename IMAGE_PULL_POLICY env var`

## Description

### Pod auto-cleanup on meeting end (`main.py`)
Completed and failed bot pods were never deleted — they accumulated in the cluster indefinitely and required manual cleanup. Now, whenever a meeting transitions to `completed` or `failed` via the status-change callback, a 10-second delayed pod stop is scheduled automatically (reusing the existing `_delayed_container_stop` helper already used for browser sessions).

- `completed` branch: cleanup scheduled after `run_all_tasks` is dispatched.
- `failed` branch: same — cleanup scheduled after post-meeting tasks.

Both paths guard on `meeting.bot_container_id` being set before scheduling.

### `IMAGE_PULL_POLICY` → `BOT_IMAGE_PULL_POLICY` (`orchestrators/kubernetes.py`)
The env var controlling the bot pod image pull policy was named `IMAGE_PULL_POLICY`, which is too generic and clashed with other services reading the same variable. Renamed to `BOT_IMAGE_PULL_POLICY`; default remains `IfNotPresent`.
