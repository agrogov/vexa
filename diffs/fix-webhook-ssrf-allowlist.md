# Fix: Webhook SSRF allowlist for internal corporate hosts

## PR Title
`fix: add WEBHOOK_ALLOWED_CIDRS env var to bypass SSRF check for trusted internal hosts`

## PR Description
Vexa's SSRF protection in `webhook_url.py` blocks any webhook URL that resolves to a private IP range
(RFC 1918). This prevents registering internal corporate endpoints as webhook targets — specifically
n8n instances that resolve to `10.x.x.x` addresses.

This change introduces an opt-in allowlist via the `WEBHOOK_ALLOWED_CIDRS` environment variable.
When set, IPs matching any listed CIDR are permitted through before the private-range block runs.
The env var is unset by default, so all existing deployments retain the original strict behaviour.

### Changes

**`libs/shared-models/shared_models/webhook_url.py`**
- At module load, parses `WEBHOOK_ALLOWED_CIDRS` (comma-separated CIDRs) into `_ALLOWED_NETWORKS`.
- `_is_blocked_ip` checks the allowlist first; a match returns `False` (allowed) immediately,
  bypassing all private-range checks.
- Both call-sites are covered: webhook registration (`admin-api`) and webhook dispatch (`bot-manager`).

**`clusters/hr/hr2-balt-ai-1/vexa/vexa-values.yaml`** (clusters-config-baltazar)
- Adds `WEBHOOK_ALLOWED_CIDRS: "10.116.37.196/32"` to `adminApi.extraEnv` and `botManager.extraEnv`.
- Host-specific `/32` rather than a broader subnet — allows only the known n8n instance IP.

### Images to rebuild
- `admin-api`
- `bot-manager`

### Security note
The allowlist is off by default. When enabled, only explicitly listed CIDRs are permitted; all other
private ranges remain blocked. The allowlist is configured at the deployment level (env var) and is
not user-controllable via the API.
