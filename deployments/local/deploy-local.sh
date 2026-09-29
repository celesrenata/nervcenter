#!/usr/bin/env bash
# T104 — NerveCenter local docker-compose deploy.
#
# Builds the api and web images (same Dockerfiles as the cluster deploy),
# then brings up the full local stack: postgres+pgvector, nats JetStream,
# one-shot alembic migrate, api, web (nginx + /api/ + /mcp/ proxy).
#
# Usage:
#   ./deployments/local/deploy-local.sh           # build images + up -d --wait
#   ./deployments/local/deploy-local.sh down      # tear down
#   ./deployments/local/deploy-local.sh logs      # tail logs
#
# Ports: api :8000, web :8080, postgres :5432, nats :4222 (client) / :8222 (monitor).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"
COMPOSE_FILE="deployments/local/docker-compose.yaml"

log()  { printf '\033[1;34m[nervcenter-local]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[nervcenter-local] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker not found on PATH"
if ! docker info >/dev/null 2>&1; then
  fail "docker daemon is not reachable.
  - macOS: open 'Docker Desktop' and wait for the whale to turn green.
  - Linux: 'sudo systemctl start docker'
  Then re-run this script."
fi
docker compose version >/dev/null 2>&1 || fail "docker compose plugin not found (Docker Desktop ships it)"

CMD="${1:-up}"

case "${CMD}" in
  up)
    GITTAG="$(git rev-parse --short HEAD 2>/dev/null || echo latest)"
    export API_IMAGE="nervecenter/api:${GITTAG}"
    export WEB_IMAGE="nervecenter/web:${GITTAG}"
    log "building ${API_IMAGE} (Dockerfile.api)"
    docker build -f Dockerfile.api -t "${API_IMAGE}" .
    log "building ${WEB_IMAGE} (web/Dockerfile)"
    docker build -f web/Dockerfile -t "${WEB_IMAGE}" web/
    docker compose -f "${COMPOSE_FILE}" up -d --wait
    log "local stack up:"
    log "  api  http://localhost:8000   (docs at /docs, health at /api/health)"
    log "  web  http://localhost:8080   (nginx proxies /api/ and /mcp/ to api)"
    ;;
  down|stop)
    docker compose -f "${COMPOSE_FILE}" down
    log "local stack down"
    ;;
  logs)
    docker compose -f "${COMPOSE_FILE}" logs --tail=100 --follow
    ;;
  *)
    fail "unknown command '${CMD}' (use: up|down|stop|logs)"
    ;;
esac
