# Helm Charts

> Shared protocol: [agents.md](../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You work on the Helm chart at `helm/charts/vexa/`. It deploys the full Vexa platform to Kubernetes. Your job is to keep the chart correct, minimal, and consistent with the services it deploys.

---

## Chart structure

```
helm/charts/vexa/
  Chart.yaml              # name: vexa, version: 0.1.0, appVersion: 0.6.0
  values.yaml             # dev defaults (local images, IfNotPresent, bundled deps)
  values-staging.yaml     # staging overrides (ghcr.io images, Always, RBAC, ingress)
  templates/
    _helpers.tpl          # ALL named templates — read this first
    deployment-*.yaml     # one file per service (13 deployments)
    statefulset-*.yaml    # postgres, minio
    service-*.yaml        # ClusterIP per deployment/statefulset
    ingress.yaml          # api-gateway ingress
    ingress-dashboard.yaml
    secret.yaml           # admin token (chart-managed)
    secret-minio.yaml
    bot-manager-rbac.yaml # ServiceAccount + Role + RoleBinding (conditional)
    job-migrations.yaml   # one-shot DB migration Job
    job-minio-bucket.yaml # post-install hook: creates MinIO bucket
    pvc-redis.yaml
    pvc-tts-voices.yaml
```

---

## Components

| Component | Default | Type | Port |
|-----------|---------|------|------|
| api-gateway | enabled | Deployment | 8000 |
| admin-api | enabled | Deployment | 8001 |
| bot-manager | enabled | Deployment | 8080 |
| transcription-collector | enabled | Deployment | 8000 |
| mcp | enabled | Deployment | 18888 |
| postgres | enabled | StatefulSet | 5432 |
| redis | enabled | Deployment | 6379 |
| dashboard | **disabled** | Deployment | 3000 |
| transcription-service | **disabled** | Deployment | 8000 |
| tts-service | **disabled** | Deployment | 8059 |
| decision-listener | **disabled** | Deployment | 8765 |
| minio | **disabled** | StatefulSet | 9000/9001 |

Every deployment/service is gated: `{{- if .Values.<component>.enabled }}`.

---

## Key patterns

### _helpers.tpl — read this before editing any template

- `vexa.componentName` — generates `{release}-vexa-{component}` names
- `vexa.labels` / `vexa.selectorLabels` — standard k8s labels
- `vexa.redisUrl` / `vexa.redisHost` / `vexa.redisPort` — auto-computed when `redis.enabled`, else from `redisConfig.*`
- `vexa.dbHost` — auto-computed when `postgres.enabled`, else from `database.host`
- `vexa.adminTokenSecretName` — resolves to `secrets.existingSecretName` or chart-managed secret
- `vexa.minioEndpoint` / `vexa.minioSecretName` — MinIO helpers

### Naming convention

All resources: `{release}-vexa-{component}` (truncated to 63 chars).  
Services address each other via DNS: `{svc}.{namespace}.svc.{clusterDomain}`.

### Secrets — 3-tier

1. **Inline** (`secrets.adminApiToken`) → chart creates Secret (dev)
2. **External** (`secrets.existingSecretName`) → reference existing Secret (prod)
3. **Per-component** (`botManager.zoom.existingSecretName`) → component-level override

### Bot orchestration modes (`botManager.orchestrator`)

- `process` — child Node.js processes, no Docker needed (dev default)
- `docker` — spawns containers via Docker socket (requires privileged)
- `kubernetes` — spawns bots as Pods, RBAC created only when `orchestrator=kubernetes` AND `createRbac=true` (staging default)

RBAC in `bot-manager-rbac.yaml`: ServiceAccount + Role (pods, pods/status CRUD+watch) + RoleBinding. Created conditionally.

### Database migrations

`job-migrations.yaml` runs a one-shot Job using the transcription-collector image. It auto-detects DB state (fresh / legacy / alembic-managed) and handles all cases. Gated by `migrations.enabled`.

### MinIO bucket

`job-minio-bucket.yaml` is a Helm post-install hook that creates the default bucket. Only runs when `minio.enabled=true`.

### Recording

Auto-enabled when `minioConfig.enabled=true`. Override with explicit `recording.enabled`.

---

## Dev vs staging differences

| Setting | values.yaml (dev) | values-staging.yaml |
|---------|-------------------|---------------------|
| Images | `vexa/*:local` | `ghcr.io/vexa-ai/*` |
| imagePullPolicy | IfNotPresent | Always |
| botManager.orchestrator | process | kubernetes |
| RBAC | false | true |
| postgres storage | 10Gi | 20Gi |
| redis storage | 2Gi | 5Gi |
| Ingress | disabled | nginx + cert-manager (`gateway.staging.vexa.ai`) |
| dashboard | disabled | enabled (`dashboard.staging.vexa.ai`) |
| migrations | disabled | enabled |
| transcriptionServiceUrl | (local) | `http://vexa-transcription-gateway:8084/v1/audio/transcriptions` |

---

## Gate

When modifying the chart, verify:
1. `helm lint helm/charts/vexa/` passes
2. `helm template helm/charts/vexa/ -f helm/charts/vexa/values.yaml` renders without error
3. `helm template helm/charts/vexa/ -f helm/charts/vexa/values-staging.yaml` renders without error
4. Any new conditional follows `{{- if .Values.<component>.enabled }}` pattern
5. New services use `vexa.componentName` helper — no hardcoded names
6. New secrets use the 3-tier pattern (inline / external / per-component)

---

## Common tasks

**Add a new service:**
1. Add `deployment-{name}.yaml` + `service-{name}.yaml` using an existing pair as template
2. Add `{name}.enabled`, `{name}.image`, `{name}.resources` to `values.yaml`
3. Add the helper-computed DNS name to any service that needs to reach it
4. Gate with `{{- if .Values.{name}.enabled }}`

**Add a new config value:**
- If it's a connection string derived from another component, add a helper to `_helpers.tpl`
- If it's an external secret, follow the `existingSecretName` pattern

**Change a port or service name:**
- Update the Service template
- Update any deployment that references it by DNS name
- Check `_helpers.tpl` for any computed URL that includes the port
