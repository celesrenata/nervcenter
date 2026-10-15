# NerveCenter Deployment Guide

Deployment of NerveCenter to the K3s cluster (nodes `gremlin-1..4`) via the
Harbor registry. This guide follows the verified workflow in
[`deployments/harbor/deploy.sh`](../deployments/harbor/deploy.sh) and the
Kubernetes manifests in [`deployments/kubernetes/`](../deployments/kubernetes/)
(kustomize base, namespace `nervecenter`).

## What gets deployed

| Workload | Kind | Image | Purpose |
|---|---|---|---|
| `postgres` | StatefulSet | `pgvector/pgvector:pg16` | Postgres + pgvector; data on `postgres-data` PVC (longhorn) |
| `nats` | Deployment | `nats:2.10-alpine` | NATS JetStream event stream (4222, monitor 8222) |
| `nervecenter-migrate` | Job | `nervecenter/api:TAG` | One-shot `python -m backend.persistence.migrate upgrade` (alembic `upgrade head`) |
| `api` | Deployment | `nervecenter/api:TAG` | FastAPI/uvicorn on `:8000`, non-root |
| `mcp` | Deployment | `nervecenter/mcp:50e4c83` | §45 MCP JSON-RPC server on `:8000` (image pinned; not rebuilt by `deploy.sh`) |
| `web` | Deployment | `nervecenter/web:TAG` | nginx SPA; proxies `/api/` + `/mcp/` to `api:8000` |
| `nervecenter-oauth` | Deployment | `oauth2-proxy:v7.15.4` | SSO gate (`:4180`) fronting `web:80` (Keycloak realm `celestium`) |
| `nervcenter-celestium` | Ingress | — | `nervecenter.celestium.life` via Traefik + cert-manager TLS |

Ingress route map (see `base/ingress.yaml`):

- `/mcp/` → `mcp:8000` — **open** (programmatic JSON-RPC; SPA never calls it)
- `/` → `nervecenter-oauth:4180` → `web:80` → SPA or `/api/` → `api:8000` — **gated**

Images: `registry.celestium.life/nervecenter/{api,web}:TAG`
(`api` from [`Dockerfile.api`](../Dockerfile.api) — `python:3.11-slim`;
`web` from [`web/Dockerfile`](../web/Dockerfile) — node:20 build → nginx:1.27-alpine).

## Prerequisites

- Running **docker** daemon (macOS: Docker Desktop). `deploy.sh` fails early
  with a clear message if the socket is unreachable.
- **kubectl** configured for the K3s cluster, with **write access**.
- **git** (for the SHA tag) and **python3** (in-pod health probe).
- **Harbor credentials**, one of:
  - `HARBOR_USER` / `HARBOR_PASS` env vars, **or**
  - an existing per-namespace `harbor-pull` secret on the cluster
    (checked in `beeflow-service`, then `harbor-service`). The script decodes
    the username from it; `docker login` then prompts for the password.

## 1. First deploy — secrets (one-time)

The app env secret is **not** in the kustomization; it is managed out-of-band.
If it has not been created yet:

```bash
cd deployments/kubernetes/base
cp secrets.yaml.example secrets.yaml   # secrets.yaml is gitignored
# edit base64 values for your real endpoints (re-encode with: printf '%s' 'value' | base64)
kubectl -n nervecenter apply -f secrets.yaml
```

The `nervecenter-env` Secret carries **both** naming schemes so the app works
until env-var names are normalized: `NERVE_DB_URL`, `NERVE_NATS_URL`,
`NERVE_OMNIROUTE_URL`, `NERVE_MOCK_INFER` (deploy contract) and
`NERVECENTER_DATABASE_URL`, `NERVECENTER_NATS_URL`, `NERVECENTER_MOCK_INFER`
(what the backend reads today). `envFrom` injects every key into the api and
migrate containers.

> SSO note: the `nervecenter-oauth` Secret (Keycloak `client-secret` /
> `cookie-secret`) must be created per the SSO activation runbook in
> [`deployments/README.md`](../deployments/README.md) before the site can sit
> behind the gate. Do **not** apply the full kustomization with the placeholder
> secret in place — unauthenticated visitors would hit a Keycloak "unknown
> client" page.

`deploy.sh` copies the per-namespace `harbor-pull` pull secret into
`nervecenter` automatically (from `beeflow-service`). Manual copy:

```bash
kubectl -n beeflow-service get secret harbor-pull -o jsonpath='{.data.\.dockerconfigjson}' \
  | base64 -d > /tmp/harbor-pull.json
kubectl -n nervecenter create secret generic harbor-pull \
  --type=kubernetes.io/dockerconfigjson \
  --from-file=.dockerconfigjson=/tmp/harbor-pull.json
```

(`base/harbor-pull.example.yaml` is a placeholder template — never apply it.)

## 2. Build + Harbor push

`deploy.sh` does this in one shot (steps 2–4 of the script):

```bash
./deployments/harbor/deploy.sh            # tag = git short SHA (fallback: latest)
TAG=1.2.3 ./deployments/harbor/deploy.sh  # explicit tag
```

Manual equivalent:

```bash
TAG="$(git rev-parse --short HEAD)"
printf '%s' "$HARBOR_PASS" | docker login registry.celestium.life -u "$HARBOR_USER" --password-stdin

docker build --platform linux/amd64 -f Dockerfile.api -t "registry.celestium.life/nervecenter/api:$TAG" .
docker build --platform linux/amd64 -f web/Dockerfile    -t "registry.celestium.life/nervecenter/web:$TAG" web/
docker push "registry.celestium.life/nervecenter/api:$TAG"
docker push "registry.celestium.life/nervecenter/web:$TAG"
```

Both images are built `linux/amd64` to match the cluster nodes. The `mcp`
image is **not** rebuilt by this pipeline — `mcp-deployment.yaml` is pinned to
the last-known-good tag.

## 3. Apply to K3s

`deploy.sh` (steps 5–7) then:

1. Ensures namespace `nervecenter` exists and copies `harbor-pull` into it.
2. Deletes the old `nervecenter-migrate` Job so migrations re-run on the new
   image (alembic `upgrade head` is idempotent — a no-op when at head).
3. Renders the kustomize tree to YAML, retags `:latest` → `$TAG` for the
   api/web images, and applies the rendered file:

```bash
kubectl -n nervecenter delete job nervecenter-migrate --ignore-not-found=true
kubectl kustomize deployments/kubernetes \
  | sed "s|registry.celestium.life/nervecenter/api:latest|registry.celestium.life/nervecenter/api:$TAG|g; \
         s|registry.celestium.life/nervecenter/web:latest|registry.celestium.life/nervecenter/web:$TAG|g" \
  > /tmp/rendered.yaml
kubectl apply -f /tmp/rendered.yaml
```

Two verified gotchas encoded in the script:

- **Render with `kubectl kustomize`, never `kubectl apply -k -o yaml`.**
  `kubectl apply` is a *live* apply even with `-o yaml`: it writes to the
  cluster first (retagging the **running** api/web to the `:latest`
  placeholder → `ImagePullBackOff`, and re-rolling the Deployments) and only
  then prints the YAML. `kubectl kustomize` is the pure, side-effect-free
  render of the identical manifest set.
- **No `kubectl apply -k --image`**: `kubectl apply` has no `--image` flag
  (`unknown flag: --image`), hence the sed retag. The sed rewrites every
  occurrence — api Deployment, migrate Job, web Deployment.

## 4. Wait + verification

`deploy.sh` (steps 7–8) waits, then probes **inside the pods**:

```bash
# 1. schema at head before the api is useful
kubectl -n nervecenter wait --for=condition=Complete job/nervecenter-migrate --timeout=300s
# 2. workloads Available
kubectl -n nervecenter wait --for=condition=Available statefulset/postgres --timeout=300s
kubectl -n nervecenter wait --for=condition=Available deployment/api      --timeout=300s
kubectl -n nervecenter wait --for=condition=Available deployment/web      --timeout=300s
kubectl -n nervecenter wait --for=condition=Available deployment/nats     --timeout=300s
# 3. pods Ready
kubectl -n nervecenter wait --for=condition=Ready pod --selector=app=api      --timeout=300s
kubectl -n nervecenter wait --for=condition=Ready pod --selector=app=web      --timeout=300s
kubectl -n nervecenter wait --for=condition=Ready pod --selector=app=postgres --timeout=300s
kubectl -n nervecenter wait --for=condition=Ready pod --selector=app=nats     --timeout=300s
```

In-pod health probes (the script runs these automatically):

```bash
API_POD=$(kubectl -n nervecenter get pod -l app=api -o jsonpath='{.items[0].metadata.name}')
WEB_POD=$(kubectl -n nervecenter get pod -l app=web -o jsonpath='{.items[0].metadata.name}')
# python:slim has no curl — use stdlib; nginx:alpine has busybox wget
kubectl -n nervecenter exec "$API_POD" -- \
  python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)'
kubectl -n nervecenter exec "$WEB_POD" -- wget -q -O - http://127.0.0.1/ >/dev/null
```

Manual checks from outside the cluster:

```bash
curl -fsS https://nervecenter.celestium.life/api/health
curl -fsSI https://nervecenter.celestium.life/ | head -1
kubectl -n nervecenter get pods svc ingress
```

TLS is issued by cert-manager (cluster issuer `celestium-le-production`) into
secret `nervecenter-celestium-tls` once DNS for `nervecenter.celestium.life`
resolves to the Traefik load-balancer IPs.

## 5. Upgrades

```bash
./deployments/harbor/deploy.sh        # new commit → new SHA tag
```

The script deletes + re-applies the migrate Job so migrations run on the new
image **before** the api/web roll. PVC data (`postgres-data`) survives
rollouts.

## 6. Rollback

Images are SHA-tagged and remain in Harbor, so rollback is re-pointing:

```bash
PREVSHA=<previous short sha>
kubectl -n nervecenter set image deployment/api api=registry.celestium.life/nervecenter/api:${PREVSHA}
kubectl -n nervecenter set image deployment/web web=registry.celestium.life/nervecenter/web:${PREVSHA}
# re-run migrations on the previous image (idempotent)
kubectl -n nervecenter delete job nervecenter-migrate
kubectl -n nervecenter apply -f deployments/kubernetes/base/migrate-job.yaml \
  --image registry.celestium.life/nervecenter/api:latest=${PREVSHA}
kubectl -n nervecenter wait --for=condition=Complete job/nervecenter-migrate --timeout=300s
```

`kubectl -n nervecenter rollout undo deployment/api` also works (single
replica), but the SHA re-point above is the deterministic path — it moves the
migration Job to the matching image too.

> **Schema downgrades are manual.** Alembic downgrades are not run by this
> pipeline — coordinate before rolling back across a migration (the previous
> image may not run on the new schema).

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ImagePullBackOff` / `ErrImagePull` | `harbor-pull` secret missing from `nervecenter`, the image wasn't pushed, or the tag doesn't exist in Harbor (check the rendered image in `kubectl -n nervecenter get deploy <name> -o yaml`). Re-run `deploy.sh` (re-copies the secret) or fix the Harbor push. |
| migrate Job failing | `kubectl -n nervecenter logs job/nervecenter-migrate` — usually the DB URL in `nervecenter-env` or postgres not up. The Job has `backoffLimit: 5`, `activeDeadlineSeconds: 120`; it will not retry forever. |
| api pod not Ready | Readiness is `GET /api/health` on `:8000`. Inspect `kubectl -n nervecenter logs deployment/api`; check `NERVE_DB_URL` / `NERVECENTER_DATABASE_URL` resolve to `postgres.nervecenter.svc`. |
| web pod not Ready | Readiness is `GET /` on `:80`; check `API_UPSTREAM`/`API_PORT` from `nervcenter-config` point at `api:8000`. |
| ingress 404 / no route | Confirm the DNS A record points at the Traefik load-balancer IPs (compare `kubectl get ingress -n beeflow-service` addresses) and that a cert is Ready: `kubectl -n nervecenter get certificates`. |
| SSO "unknown client" / gate loop | The Keycloak `nervecenter` client doesn't exist or the `nervecenter-oauth` Secret still has the placeholder `client-secret` — see the SSO activation runbook in `deployments/README.md`. Do not apply the ingress re-point before steps 1–2 there. |
| `unknown flag: --image` on apply | `kubectl apply -k --image` doesn't exist; use the `kubectl kustomize` + sed retag from §3. Never `kubectl apply -k -o yaml` (live apply — see gotchas). |
| Docker daemon errors on start | `deploy.sh` tells you how to fix it (Docker Desktop on macOS / `systemctl start docker` on Linux), then re-run. |

Useful inspection commands:

```bash
kubectl -n nervecenter get pods
kubectl -n nervecenter describe pod <pod>          # events: pull, probe, scheduling
kubectl -n nervecenter logs -f deployment/api
kubectl -n nervecenter rollout status deployment/api
kubectl -n nervecenter get secret harbor-pull -o jsonpath='{.type}'   # → kubernetes.io/dockerconfigjson
```

## Related

- [`deployments/README.md`](../deployments/README.md) — full operational doc
  incl. SSO (Keycloak) activation runbook.
- [`deployments/local/`](../deployments/local/) — docker-compose local dev
  stack (`deploy-local.sh up/logs/down`).
