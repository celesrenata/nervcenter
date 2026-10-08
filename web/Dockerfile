# syntax=docker/dockerfile:1
# NerveCenter Web — node:20 build -> nginx:1.27-alpine SPA server with
# /api/ + /mcp/ reverse proxy to the api service.
#
# Build (from repo root, context = web/):
#   docker build -f web/Dockerfile -t registry.celestium.life/nervecenter/web:TAG web/
#
# The upstream is set at container start (env): k8s ConfigMap sets
# API_UPSTREAM=api.nervecenter.svc; docker-compose sets API_UPSTREAM=api.

FROM node:20 AS build
WORKDIR /app
ENV npm_config_fund=false \
    npm_config_audit=false \
    npm_config_update-notifier=false

# Install deps before any source copy for maximal layer caching.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# T206 — bake real-mode API base into the production bundle.
# Vite only reads VITE_API_BASE from the build-time env; without it the bundle
# defaults to mock mode (see web/src/api/client.ts: useMockMode = !VITE_API_BASE).
# nginx reverse-proxies /api/ + /mcp/ same-origin (see nginx.conf.template), so
# /api is the correct base. Overridable at build time:
#   docker build --build-arg VITE_API_BASE=... -f web/Dockerfile -t web:TAG web/
ARG VITE_API_BASE=/api
ENV VITE_API_BASE="${VITE_API_BASE}"

# `npm run build` = `tsc && vite build` -> dist/
RUN npm run build

# Fail the build when the bundle is missing.
RUN test -d dist && test -n "$(ls -A dist)"

FROM nginx:1.27-alpine

# Upstream defaults; overridden at runtime via container env.
ENV API_UPSTREAM=api.nervecenter.svc \
    API_PORT=8000

# Full main config template + scoped-envsubst entrypoint (see entrypoint.sh).
COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY entrypoint.sh /entrypoint.sh

# SPA bundle (root index + hashed assets).
COPY --from=build /app/dist/ /usr/share/nginx/html/

EXPOSE 80

# nginx master must be root to bind :80; workers drop privileges to `nginx`
# per the stock config. (k8s web pod does not set runAsNonRoot for this reason.)
USER root

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["/bin/sh", "-c", "wget -q -O /dev/null http://127.0.0.1/ || exit 1"]

ENTRYPOINT ["/entrypoint.sh"]
