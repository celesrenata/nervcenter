# NerveCenter Deployment

| Target | Where | How |
|---|---|---|
| K3s via Harbor | [`deployments/kubernetes/`](deployments/kubernetes/) | [`deployments/harbor/deploy.sh`](deployments/harbor/deploy.sh) |
| Local (docker compose) | [`deployments/local/`](deployments/local/) | [`deployments/local/deploy-local.sh`](deployments/local/deploy-local.sh) |

Images: `registry.celestium.life/nervecenter/api:TAG` (from
[`Dockerfile.api`](../Dockerfile.api), `python:3.11-slim`, non-root uvicorn on :8000)
and `registry.celestium.life/nervecenter/web:TAG` (node:20 build →
nginx:1.27-alpine SPA + `/api/` + `/mcp/` reverse proxy, [`web/Dockerfile`](../web/Dockerfile)).

## Prerequisites

- Running docker daemon (macOS: Docker Desktop). If the socket is missing the
  scripts print a clear message and exit — start Docker and re-run.
- `kubectl` configured for the K3s cluster (gremlin-1..4), with write access.
- Harbor credentials: `HARBOR_USER`/`HARBOR_PASS` env vars, **or** an existing
  per-namespace `harbor-pull` secret on the cluster (the script decodes the
  username from it; `docker login` then prompts for the password).
- The image must be built before a real deploy (T201). Do not run `deploy.sh`
  in CI without images.

## First deploy

1. **Create the app env secret** if it has not been created yet:

   ```bash
   cd deployments/kubernetes/base
   cp secrets.yaml.example secrets.yaml   # secrets.yaml is gitignored
   # edit base64 values for your real endpoints (see the header in the file)
   kubectl -n nervecenter apply -f secrets.yaml
   ```

   The secret carries **both** naming schemes: `NERVE_DB_URL`,
   `NERVE_NATS_URL`, `NERVE_OMNIROUTE_URL`, `NERVE_MOCK_INFER` (T104 deploy
   contract) and `NERVECENTER_DATABASE_URL`, `NERVECENTER_NATS_URL`,
   `NERVECENTER_MOCK_INFER` (what the backend reads today —
   [`backend/persistence/connection.py`](../backend/persistence/connection.py),
   [`backend/events/nats_client.py`](../backend/events/nats_client.py)).
   `envFrom` injects every key into the api & migrate containers.

2. **Run the deploy** (builds, pushes, ensures ns + pulls the harbor-pull
   secret, re-runs the alembic migration Job, applies the kustomize base
   retagged with the build, waits for readiness):

   ```bash
   ./deployments/harbor/deploy.sh
   ```

   Image tag = `git rev-parse --short HEAD` (override with `TAG=...`). The
   kustomize `--image` transformer rewrites the `:latest` placeholder in the
   api/web/migrate objects to the build tag before apply.

3. **Verify** (the script already probes in-pod; manual checks):

   ```bash
   curl -fsS https://nervecenter.celestium.life/api/health
   curl -fsSI https://nervecenter.celestium.life/ | head -1
   kubectl -n nervecenter get pods,svc,ingress
   ```

### Ingress host & TLS

- Host: `nervecenter.celestium.life` — `/` → web (nginx SPA), `/api/` → api,
  `/mcp/` → api ([`ingress.yaml`](kubernetes/base/ingress.yaml)).
- `ingressClassName: traefik`; TLS is issued by cert-manager via
  `cert-manager.io/cluster-issuer: celestium-le-production` into secret
  `nervecenter-celestium-tls` (mirrors the beeflow/comfyui pattern).
- Point DNS at the same Traefik load-balancer IPs the other hosts use; cert
  is provisioned automatically once DNS resolves.

## Upgrades

```bash
./deployments/harbor/deploy.sh        # new commit → new sha tag
```

The script deletes + re-applies the `nervecenter-migrate` Job so migrations
run on the new image before the api/web roll. `alembic upgrade head` is
idempotent (no-op when the schema is at head). PVC data (`postgres-data`,
longhorn) survives rollouts.

## Rollback

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
replica), but the SHA re-point above is the deterministic path (it moves the
migration Job to the matching image too). Schema downgrades are manual
(alembic downgrades are not run by this pipeline) — coordinate with T101
before rolling back across a migration.

## Copying the Harbor pull secret per namespace

Every namespace carries its own `harbor-pull`
(`kubernetes.io/dockerconfigjson`). `deploy.sh` copies it automatically when
`nervecenter` lacks the secret. By hand:

```bash
# source secret from any ns that already has the same registry auth
kubectl -n beeflow-service get secret harbor-pull -o jsonpath='{.data.\.dockerconfigjson}' \
  | base64 -d > /tmp/harbor-pull.json
kubectl -n nervecenter delete secret harbor-pull --ignore-not-found
kubectl -n nervecenter create secret generic harbor-pull \
  --type=kubernetes.io/dockerconfigjson \
  --from-file=.dockerconfigjson=/tmp/harbor-pull.json
```

Verify: `kubectl -n nervecenter get secret harbor-pull -o jsonpath='{.type}'`
→ `kubernetes.io/dockerconfigjson`.
[`harbor-pull.example.yaml`](kubernetes/base/harbor-pull.example.yaml) in
`base/` is a template only (placeholder body — never apply it).

## Local development

```bash
./deployments/local/deploy-local.sh          # build images + up -d --wait
./deployments/local/deploy-local.sh logs     # tail logs
./deployments/local/deploy-local.sh down     # tear down
```

Stack (see [`docker-compose.yaml`](local/docker-compose.yaml)):
`postgres` (pgvector/pgvector:pg16, :5432), `nats` (:4222/:8222 JetStream),
`migrate` (one-shot `python -m backend.persistence.migrate upgrade`),
`api` (uvicorn :8000), `web` (nginx :8080, proxies `/api/` + `/mcp/` to `api`).

## Troubleshooting

- `ImagePullBackOff` / `ErrImagePull` — `harbor-pull` secret missing or push
  failed; re-run `deploy.sh` (re-copies the secret) or fix the Harbor push.
- migrate Job failing — `kubectl -n nervecenter logs job/nervecenter-migrate`
  (usually DB URL in `nervecenter-env`, or postgres not up); the Job has
  `backoffLimit: 5`, `activeDeadlineSeconds: 120`.
- api pod not Ready — readiness is `GET /api/health` (:8000); inspect
  `kubectl -n nervecenter logs deployment/api`.
- ingress 404 — confirm the DNS A record points at the Traefik load-balancer
  IPs (compare `kubectl get ingress -n beeflow-service` addresses) and the
  cert is Ready: `kubectl -n nervecenter get certificates