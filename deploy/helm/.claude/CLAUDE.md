# Helm Deployment Testing Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Why
You validate the Helm/K8s deployment. You know the charts, values, and how to verify the stack on a real cluster.

## What
You test the Helm charts against a K8s cluster.

### Charts
- `charts/vexa/` -- full production (all services as separate pods)
- `charts/vexa-lite/` -- single-pod deployment

### What "working" means
1. `helm template` renders without errors
2. `helm install --dry-run` succeeds
3. All pods Running after deploy
4. All services have endpoints
5. Ingress routes correctly
6. Secrets are created
7. PVCs bound
8. Bot RBAC works (can spawn pods)
9. Inter-service connectivity
10. Health endpoints respond

### Gate (local)
Helm template renders without errors and pods start successfully. PASS: `helm template` produces valid YAML, `helm install --dry-run` succeeds, pods reach Running state. FAIL: template errors, invalid manifests, or pods in CrashLoopBackOff.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

## How
```bash
export KUBECONFIG=/home/dima/.kube/config

# Template validation (no cluster needed)
helm template vexa deploy/helm/charts/vexa/ -f values.yaml

# Dry run
helm install vexa deploy/helm/charts/vexa/ --dry-run -f values.yaml

# Deploy
helm upgrade --install vexa deploy/helm/charts/vexa/ -f values.yaml

# Verify
kubectl get pods
kubectl get svc
kubectl get ingress

# Health
for svc in vexa-vexa-api-gateway vexa-vexa-admin-api vexa-vexa-bot-manager; do
  kubectl exec deploy/$svc -- curl -s localhost:8000/ 2>/dev/null | head -3
done
```

### Docs are your test specs

The "What working means" list above is your test specification. When charts change and the docs update, your verification criteria change with it. Don't limit yourself to the script — read the README, derive what should be true, verify it.

### After every test run
1. Update the README if specs were unclear
2. Add unexpected findings to `tests/findings.md`
3. Note what you couldn't test and why
4. The goal: each run makes the docs better, which makes the next run better

