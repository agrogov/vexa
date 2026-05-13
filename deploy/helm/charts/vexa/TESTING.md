# Helm Chart Testing Plan

Validation checklist for the Vexa Helm chart after modifications.

## Prerequisites

```bash
CHART=deploy/helm/charts/vexa
```

## 1. Basic rendering

```bash
helm template vexa $CHART 2>&1 | grep -c '^---'
# Expected: 24 resources (default values, no optional services enabled)
# Must render with zero errors
```

## 2. minio-init Job

```bash
helm template vexa $CHART 2>&1 | awk '/job-minio-init.yaml/{f=1} f{print} f && /^---$/{f=0}'
```

Verify:
- Command script has poll-until-ready loop (`for attempt in $(seq 1 24)`) with `mc admin info` health check — NOT `sleep 5`
- `helm.sh/hook-delete-policy` is `before-hook-creation` — NOT `before-hook-creation,hook-succeeded`
- Template file contains `{{- with .Values.global.nodeSelector }}`, `{{- with .Values.global.tolerations }}`, `{{- with .Values.global.affinity }}` blocks

## 3. Migrations Job

```bash
helm template vexa $CHART --set migrations.enabled=true 2>&1 | awk '/job-migrations.yaml/{f=1} f{print} f && /^---$/{f=0}'
```

Verify:
- Job name includes version suffix (e.g. `migrations-0-10-5-2`)
- Has BOTH `helm.sh/hook: pre-upgrade` AND `argocd.argoproj.io/hook: PreSync` annotations
- Not rendered when `migrations.enabled=false` (default)

## 4. Redis Deployment

```bash
helm template vexa $CHART 2>&1 | awk '/deployment-redis.yaml/{f=1} f && /args:/{a=1} a{print} f && /^---$/{f=0}'
```

Verify args include:
- `--appendonly yes`
- `--appendfsync everysec`
- `--stop-writes-on-bgsave-error no`
- `--maxmemory 1gb`
- `--maxmemory-policy allkeys-lru`

## 5. DB pool sizing defaults

```bash
for svc in admin-api meeting-api runtime-api; do
  echo "=== $svc ==="
  helm template vexa $CHART 2>&1 | awk -v s="$svc" '/name:.*'$svc'$/{f=1} f && /DB_POOL/{print} f && /^---$/{f=0}'
done
```

Expected:
- admin-api: DB_POOL_SIZE=10, DB_MAX_OVERFLOW=5, DB_POOL_TIMEOUT=10
- meeting-api: DB_POOL_SIZE=20, DB_MAX_OVERFLOW=20, DB_POOL_TIMEOUT=10
- runtime-api: DB_POOL_SIZE=10, DB_MAX_OVERFLOW=5, DB_POOL_TIMEOUT=10

## 6. Orphaned templates removed

```bash
ls deploy/helm/charts/vexa/templates/configmap-runtime-profiles.yaml 2>&1
# Expected: No such file or directory
```

## 7. Runtime profiles ConfigMap

```bash
helm template vexa $CHART 2>&1 | awk '/configmap-runtime-api-profiles.yaml/{f=1} f{print} f && /^---$/{f=0}'
```

Verify:
- ConfigMap renders with key `profiles.yaml`
- Contains `meeting`, `browser-session`, and `agent` profiles
- Bot env propagation present: `MEETING_API_URL`, `RECORDING_ENABLED`, `STORAGE_BACKEND`, `MINIO_*`

## 8. Deployment strategies

```bash
helm template vexa $CHART 2>&1 | grep -B5 'maxSurge: 0' | grep 'name:'
```

All stateless Deployments should have `RollingUpdate` with `maxSurge: 0, maxUnavailable: 1`:
- admin-api, api-gateway, mcp, meeting-api, runtime-api, calendar-service (when enabled), dashboard (when enabled), pgbouncer (when enabled), transcription-service (when enabled)

Exceptions (use `Recreate`): redis, tts-service (single-replica with PVC)

## 9. Anti-affinity on stateful pods

```bash
helm template vexa $CHART 2>&1 | grep -B10 'podAntiAffinity' | grep 'name:'
```

Expected on: redis, minio, postgres, tts-service

## 10. PgBouncer conditional rendering

```bash
# Disabled (default) — should NOT render
helm template vexa $CHART 2>&1 | grep -c 'pgbouncer'
# Expected: 0

# Enabled — should render Deployment + Service
helm template vexa $CHART --set pgbouncer.enabled=true 2>&1 | grep -c 'pgbouncer'
# Expected: >0
```

## 11. No rendering errors or warnings

```bash
helm template vexa $CHART --debug 2>&1 | grep -i '^Error' || echo "No errors"
```

## 12. No duplicate ConfigMaps

```bash
helm template vexa $CHART 2>&1 | grep 'kind: ConfigMap' -A2 | grep 'name:' | sort | uniq -c | sort -rn
# All counts should be 1
```

## Testing with production values overlay

```bash
helm template vexa $CHART -f vexa2-values.yaml --namespace vexa2 2>&1 | grep -c '^---'
# Should render without errors
# Resource count will be higher (more services enabled)
```
