# Security Audit

Run a comprehensive security audit across the Vexa repo. Each check is PASS/FAIL with evidence. Results logged to test.log with `[security-audit]` prefix.

## Usage

Run from repo root `/home/dima/dev/vexa/`.

## Checks

### 1. Secrets in Git History

Search for leaked secrets across all branches. Exclude .env templates and examples.

```bash
echo "=== Secrets in git history ==="
HITS=$(git log -p --all -S 'sk_live\|sk_test\|ADMIN_API_TOKEN=\|password=' -- ':!.env*' ':!env-example' ':!*.example' ':!*.sample' 2>/dev/null | head -50)
if [ -z "$HITS" ]; then
  echo "[$(date -Iseconds)] [security-audit] PASS: no secrets found in git history" >> /home/dima/dev/vexa/test.log
  echo "PASS: no secrets in git history"
else
  echo "[$(date -Iseconds)] [security-audit] FAIL: potential secrets in git history" >> /home/dima/dev/vexa/test.log
  echo "FAIL: potential secrets in git history:"
  echo "$HITS"
fi
```

Also check for high-entropy strings and common secret patterns:

```bash
echo "=== Broad secret patterns ==="
git log -p --all -S 'BEGIN RSA PRIVATE\|BEGIN OPENSSH PRIVATE\|AKIA[0-9A-Z]\|ghp_\|gho_\|glpat-\|xox[bpoas]-' -- ':!.env*' ':!*.example' 2>/dev/null | head -30
```

### 2. Secrets in Logs and Findings

Test outputs and logs should never contain secrets.

```bash
echo "=== Secrets in test.log and findings ==="
LOGFILES=$(find /home/dima/dev/vexa -name "test.log" -o -name "findings.md" 2>/dev/null)
for f in $LOGFILES; do
  HITS=$(grep -iE 'sk_live|sk_test|password=.{8,}|token=[a-zA-Z0-9]{20,}|Bearer [a-zA-Z0-9]{20,}' "$f" 2>/dev/null | head -5)
  if [ -n "$HITS" ]; then
    echo "[$(date -Iseconds)] [security-audit] FAIL: secrets found in $f" >> /home/dima/dev/vexa/test.log
    echo "FAIL: secrets in $f"
    echo "$HITS"
  fi
done
echo "PASS: no secrets in logs/findings (if no FAIL above)"
```

### 3. Docker Images — Baked-in Secrets

Check running containers for secrets in environment variables and image layers.

```bash
echo "=== Docker env var audit ==="
for container in $(docker ps --format '{{.Names}}' 2>/dev/null | grep -i vexa); do
  ENVS=$(docker inspect "$container" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null)
  LEAKS=$(echo "$ENVS" | grep -iE 'password=.{8,}|secret=.{8,}|token=.{20,}|sk_live|sk_test' | grep -v '=${' | head -5)
  if [ -n "$LEAKS" ]; then
    echo "[$(date -Iseconds)] [security-audit] FAIL: secrets baked into container $container" >> /home/dima/dev/vexa/test.log
    echo "FAIL: $container has baked-in secrets:"
    echo "$LEAKS"
  else
    echo "PASS: $container env vars clean"
  fi
done
```

```bash
echo "=== Docker layer history ==="
for image in $(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -i vexa | head -10); do
  LAYER_LEAKS=$(docker history "$image" --no-trunc 2>/dev/null | grep -iE 'password|secret|token|sk_live' | head -3)
  if [ -n "$LAYER_LEAKS" ]; then
    echo "[$(date -Iseconds)] [security-audit] FAIL: secrets in image layers of $image" >> /home/dima/dev/vexa/test.log
    echo "FAIL: $image has secrets in layers"
  fi
done
```

### 4. .env Template Audit

Ensure env-example and .env templates have placeholder values, not real secrets.

```bash
echo "=== .env template audit ==="
for f in $(find /home/dima/dev/vexa -name 'env-example' -o -name '.env.example' -o -name '.env.template' 2>/dev/null); do
  REAL=$(grep -E '(password|secret|token|key)=' "$f" | grep -vE '=(\$\{|changeme|your-|xxx|placeholder|<|TODO|REPLACE)' | grep -E '=.{8,}' | head -5)
  if [ -n "$REAL" ]; then
    echo "[$(date -Iseconds)] [security-audit] FAIL: real secrets in template $f" >> /home/dima/dev/vexa/test.log
    echo "FAIL: real secrets in $f"
    echo "$REAL"
  else
    echo "PASS: $f uses placeholder values"
  fi
done
```

### 5. Auth Enforcement — Unauthenticated Requests

Every exposed API endpoint must reject requests without a valid token.

```bash
echo "=== Auth enforcement ==="
ENDPOINTS=(
  "http://localhost:8056/api/meetings|api-gateway"
  "http://localhost:8056/api/transcripts|api-gateway"
  "http://localhost:8056/api/bots|api-gateway"
  "http://localhost:8057/api/users|admin-api"
  "http://localhost:8057/api/tokens|admin-api"
  "http://localhost:8123/health|transcription-collector"
)

for entry in "${ENDPOINTS[@]}"; do
  URL="${entry%%|*}"
  SVC="${entry##*|}"
  STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$URL" 2>/dev/null)
  if [ "$STATUS" = "000" ]; then
    echo "SKIP: $SVC ($URL) — not reachable"
  elif echo "$STATUS" | grep -qE '^(401|403|422)$'; then
    echo "PASS: $SVC rejects unauthenticated ($STATUS)"
  elif echo "$URL" | grep -q '/health'; then
    echo "PASS: $SVC health endpoint is public ($STATUS) — expected"
  else
    echo "[$(date -Iseconds)] [security-audit] FAIL: $SVC allows unauthenticated access ($STATUS) at $URL" >> /home/dima/dev/vexa/test.log
    echo "FAIL: $SVC allows unauthenticated access — got $STATUS at $URL"
  fi
done
```

### 6. CORS Configuration

Check that CORS isn't wide open.

```bash
echo "=== CORS audit ==="
# Check code for wildcard CORS
CORS_WILD=$(grep -rn 'allow_origins.*\*\|Access-Control-Allow-Origin.*\*\|cors.*origin.*\*' /home/dima/dev/vexa/services/ --include='*.py' --include='*.ts' --include='*.js' 2>/dev/null | grep -v node_modules | grep -v '.test.' | head -10)
if [ -n "$CORS_WILD" ]; then
  echo "[$(date -Iseconds)] [security-audit] FAIL: wildcard CORS origins found" >> /home/dima/dev/vexa/test.log
  echo "FAIL: wildcard CORS origins:"
  echo "$CORS_WILD"
else
  echo "PASS: no wildcard CORS origins"
fi

# Runtime check
CORS_RESP=$(curl -s -I -H "Origin: https://evil.com" --max-time 5 http://localhost:8056/api/meetings 2>/dev/null | grep -i 'access-control-allow-origin')
if echo "$CORS_RESP" | grep -q 'evil.com\|\*'; then
  echo "[$(date -Iseconds)] [security-audit] FAIL: CORS allows arbitrary origins at runtime" >> /home/dima/dev/vexa/test.log
  echo "FAIL: CORS reflects arbitrary origin: $CORS_RESP"
else
  echo "PASS: CORS does not reflect arbitrary origin"
fi
```

### 7. Rate Limiting

Check that rate limiting exists in code.

```bash
echo "=== Rate limiting ==="
RATE_CODE=$(grep -rn 'rate.limit\|RateLimit\|throttle\|slowDown\|limiter' /home/dima/dev/vexa/services/ --include='*.py' --include='*.ts' --include='*.js' 2>/dev/null | grep -v node_modules | grep -v '.test.' | head -10)
if [ -n "$RATE_CODE" ]; then
  echo "PASS: rate limiting code found:"
  echo "$RATE_CODE"
else
  echo "[$(date -Iseconds)] [security-audit] FAIL: no rate limiting code found in services" >> /home/dima/dev/vexa/test.log
  echo "FAIL: no rate limiting code found — all endpoints are unbounded"
fi
```

### 8. Token Scoping Enforcement

Check that token scoping goes beyond prefix matching — actual scope checks in middleware/handlers.

```bash
echo "=== Token scoping ==="
SCOPE_CODE=$(grep -rn 'scope\|permission\|authorize\|has_access\|check_scope\|required_scopes' /home/dima/dev/vexa/services/ --include='*.py' --include='*.ts' --include='*.js' 2>/dev/null | grep -v node_modules | grep -v '.test.' | grep -v 'import' | head -15)
if [ -n "$SCOPE_CODE" ]; then
  echo "FOUND: token scoping code — review manually:"
  echo "$SCOPE_CODE"
else
  echo "[$(date -Iseconds)] [security-audit] FAIL: no token scoping enforcement found" >> /home/dima/dev/vexa/test.log
  echo "FAIL: no token scoping enforcement found"
fi
```

### 9. Injection Patterns

#### SQL Injection (Python)

```bash
echo "=== SQL injection patterns ==="
# Raw string formatting in SQL queries (Python)
SQL_INJ=$(grep -rn 'f".*SELECT\|f".*INSERT\|f".*UPDATE\|f".*DELETE\|\.format(.*SELECT\|%s.*execute\|\.execute(f"' /home/dima/dev/vexa/services/ --include='*.py' 2>/dev/null | grep -v '.test.' | grep -v 'alembic' | head -10)
if [ -n "$SQL_INJ" ]; then
  echo "[$(date -Iseconds)] [security-audit] FAIL: potential SQL injection — f-string or .format() in SQL" >> /home/dima/dev/vexa/test.log
  echo "FAIL: potential SQL injection vectors:"
  echo "$SQL_INJ"
else
  echo "PASS: no obvious SQL injection patterns in Python"
fi
```

#### Command Injection (Python)

```bash
echo "=== Command injection patterns ==="
CMD_INJ=$(grep -rn 'subprocess.*shell=True\|os\.system(\|os\.popen(' /home/dima/dev/vexa/services/ --include='*.py' 2>/dev/null | grep -v '.test.' | head -10)
if [ -n "$CMD_INJ" ]; then
  echo "[$(date -Iseconds)] [security-audit] FAIL: potential command injection — shell=True or os.system" >> /home/dima/dev/vexa/test.log
  echo "FAIL: potential command injection:"
  echo "$CMD_INJ"
else
  echo "PASS: no obvious command injection patterns"
fi
```

#### XSS (TypeScript/JavaScript)

```bash
echo "=== XSS patterns ==="
XSS=$(grep -rn 'dangerouslySetInnerHTML\|innerHTML\s*=\|document\.write(' /home/dima/dev/vexa/services/ --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' 2>/dev/null | grep -v node_modules | grep -v '.test.' | head -10)
if [ -n "$XSS" ]; then
  echo "[$(date -Iseconds)] [security-audit] FAIL: potential XSS — dangerouslySetInnerHTML or innerHTML" >> /home/dima/dev/vexa/test.log
  echo "FAIL: potential XSS vectors:"
  echo "$XSS"
else
  echo "PASS: no obvious XSS patterns"
fi
```

### 10. Dependency CVEs

```bash
echo "=== Dependency CVEs ==="
# npm audit (if available)
for pkg in $(find /home/dima/dev/vexa/services -name 'package-lock.json' -not -path '*/node_modules/*' 2>/dev/null); do
  DIR=$(dirname "$pkg")
  echo "--- npm audit: $DIR ---"
  (cd "$DIR" && npm audit --json 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    vulns = data.get('vulnerabilities', {})
    critical = [k for k,v in vulns.items() if v.get('severity') == 'critical']
    high = [k for k,v in vulns.items() if v.get('severity') == 'high']
    if critical or high:
        print(f'FAIL: {len(critical)} critical, {len(high)} high')
        for c in critical[:5]: print(f'  CRITICAL: {c}')
        for h in high[:5]: print(f'  HIGH: {h}')
    else:
        print(f'PASS: no critical/high vulns ({len(vulns)} total)')
except: print('SKIP: could not parse npm audit output')
" 2>/dev/null) || echo "SKIP: npm audit failed"
done

# pip audit (if available)
if command -v pip-audit &>/dev/null; then
  for req in $(find /home/dima/dev/vexa/services -name 'requirements*.txt' 2>/dev/null | head -5); do
    echo "--- pip-audit: $req ---"
    pip-audit -r "$req" --desc 2>/dev/null | head -20
  done
else
  echo "SKIP: pip-audit not installed (pip install pip-audit)"
fi
```

### 11. Container Security

```bash
echo "=== Container security ==="
for container in $(docker ps --format '{{.Names}}' 2>/dev/null | grep -i vexa); do
  USER=$(docker inspect "$container" --format '{{.Config.User}}' 2>/dev/null)
  CAPS=$(docker inspect "$container" --format '{{.HostConfig.CapAdd}}' 2>/dev/null)
  PRIV=$(docker inspect "$container" --format '{{.HostConfig.Privileged}}' 2>/dev/null)

  ISSUES=""
  if [ -z "$USER" ] || [ "$USER" = "root" ] || [ "$USER" = "0" ]; then
    ISSUES="running as root"
  fi
  if [ "$PRIV" = "true" ]; then
    ISSUES="$ISSUES, privileged mode"
  fi
  if [ -n "$CAPS" ] && [ "$CAPS" != "[]" ]; then
    ISSUES="$ISSUES, extra caps: $CAPS"
  fi

  if [ -n "$ISSUES" ]; then
    echo "[$(date -Iseconds)] [security-audit] FAIL: $container — $ISSUES" >> /home/dima/dev/vexa/test.log
    echo "FAIL: $container — $ISSUES"
  else
    echo "PASS: $container — non-root, no extra caps"
  fi
done
```

## Summary

After running all checks, log a summary:

```bash
PASS_COUNT=$(grep -c '\[security-audit\] PASS' /home/dima/dev/vexa/test.log 2>/dev/null || echo 0)
FAIL_COUNT=$(grep -c '\[security-audit\] FAIL' /home/dima/dev/vexa/test.log 2>/dev/null || echo 0)
echo "[$(date -Iseconds)] [security-audit] SUMMARY: $PASS_COUNT passed, $FAIL_COUNT failed" >> /home/dima/dev/vexa/test.log
echo "=== Security Audit Complete: $PASS_COUNT passed, $FAIL_COUNT failed ==="
```

Save detailed findings to `/home/dima/dev/vexa/security/tests/findings.md`.
