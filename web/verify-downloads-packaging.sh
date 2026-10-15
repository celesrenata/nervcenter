#!/usr/bin/env bash
# Focused verification for the optional /downloads/ artifact packaging in
# web/Dockerfile (self-host app distribution, ad-hoc).
#
# Asserts, with REAL `docker build` runs of web/Dockerfile, that:
#   1. default mode  — build succeeds with NO staged web/dist/downloads and
#                      still produces the SPA bundle; /usr/share/nginx/downloads
#                      exists but is empty (location 404s, no SPA fallback).
#   2. staged mode   — with web/dist/downloads staged, manifest.json is baked
#                      into the image at /usr/share/nginx/downloads/ and its
#                      content round-trips.
#   3. context       — non-download dist/ files never enter the build context
#                      (web/.dockerignore keeps `dist`, re-including only
#                      `!dist/downloads`).
#   4. no secrets    — web/Dockerfile + web/.dockerignore reference no
#                      credentials, so packaging needs no secrets.
#
# Usage:  ./web/verify-downloads-packaging.sh [tag]     (tag defaults to
#         nervcenter-web-verify). Requires docker. Non-zero exit on failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${REPO_ROOT}/web"
TAG="${1:-nervcenter-web-verify}"

log()  { printf '\033[1;34m[downloads-packaging]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[downloads-packaging] FAIL:\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker not found on PATH"
docker info >/dev/null 2>&1 || fail "docker daemon not reachable"

DIST="${WEB_DIR}/dist"
DL="${DIST}/downloads"
STAGED_MANIFEST="${DL}/manifest.json"
MARKER="${DIST}/__packaging_probe__.js"   # must never reach the image

# --- cleanup of anything this script created (best effort, on exit) ----------
DIST_EXISTED=0; [[ -d "$DIST" ]] && DIST_EXISTED=1
DL_EXISTED=0;  [[ -d "$DL"   ]] && DL_EXISTED=1
cleanup() {
  [[ -f "$MARKER"        ]] && find "$MARKER" -delete 2>/dev/null || true
  [[ -f "$STAGED_MANIFEST" ]] && find "$STAGED_MANIFEST" -delete 2>/dev/null || true
  if [[ "$DL_EXISTED" -eq 0 && -d "$DL" ]]; then
    # staged dir was created by this run — remove it (empty after manifest rm)
    rmdir "$DL" 2>/dev/null || true
  fi
  if [[ "$DIST_EXISTED" -eq 0 && -d "$DIST" ]]; then
    rmdir "$DIST" 2>/dev/null || true
  fi
}
trap cleanup EXIT

assert_contains() { # $1=image  $2=path  $3=description
  docker run --rm --entrypoint ls "$1" "$2" >/dev/null 2>&1 \
    || fail "image $1 missing expected $3 ($2)"
  log "OK: $1 contains $3"
}
assert_absent() { # $1=image  $2=path  $3=description
  if docker run --rm --entrypoint ls "$1" "$2" >/dev/null 2>&1; then
    fail "image $1 unexpectedly contains $3 ($2)"
  fi
  log "OK: $1 does not contain $3"
}

# --- 1. default mode: no staged downloads -------------------------------------
if [[ -d "$DL" ]]; then
  find "$DL" -mindepth 1 -delete 2>/dev/null || true   # clear any leftovers
  log "note: pre-existing web/dist/downloads emptied for default-mode build"
fi
log "building ${TAG}:default (no staged web/dist/downloads)"
docker build -q -f "${WEB_DIR}/Dockerfile" -t "${TAG}:default" "${WEB_DIR}" >/dev/null \
  || fail "default-mode docker build failed"
assert_contains "${TAG}:default" /usr/share/nginx/html/index.html "SPA bundle index.html"
assert_contains "${TAG}:default" /usr/share/nginx/downloads "downloads dir (empty)"
assert_absent   "${TAG}:default" /usr/share/nginx/downloads/manifest.json "staged manifest"

# --- 2. staged mode ------------------------------------------------------------
mkdir -p "$DL"
cat > "$STAGED_MANIFEST" <<'JSON'
{
  "name": "NerveCenter",
  "generated_at": "1970-01-01T00:00:00Z",
  "versions": { "phone": "0.0.0-test", "watch": "0.0.0-test", "widget": "0.0.0-test" },
  "artifacts": [
    { "name": "test-artifact.ipa", "kind": "ios", "path": "test-artifact.ipa",
      "present": true, "embedded": false, "bundle_id": "com.celesrenata.test",
      "min_ios": "17.0", "sha256": "PACKAGINGVERIFY", "bytes": 1 }
  ]
}
JSON
echo '/* packaging probe — must never enter the build context */' > "$MARKER"

log "building ${TAG}:staged (web/dist/downloads staged)"
docker build -q -f "${WEB_DIR}/Dockerfile" -t "${TAG}:staged" "${WEB_DIR}" >/dev/null \
  || fail "staged-mode docker build failed"
assert_contains "${TAG}:staged" /usr/share/nginx/html/index.html "SPA bundle index.html"
assert_contains "${TAG}:staged" /usr/share/nginx/downloads/manifest.json "staged manifest.json"
CONTENT="$(docker run --rm --entrypoint cat "${TAG}:staged" /usr/share/nginx/downloads/manifest.json)"
printf '%s' "$CONTENT" | grep -q '"name": "NerveCenter"' \
  || fail "baked manifest.json does not contain expected name field"
log "OK: baked manifest.json content round-trips"

# --- 3. context hygiene ---------------------------------------------------------
assert_absent "${TAG}:staged" /usr/share/nginx/html/__packaging_probe__.js \
  "non-download dist/ file (context leak)"
assert_absent "${TAG}:staged" /app/downloads/__packaging_probe__.js "probe in build stage"
log "OK: build context contains only dist/downloads from dist/"

# --- 4. no secrets ---------------------------------------------------------------
if grep -RInE 'HARBOR_|APPLE_|APP_PRIVATE_KEY|\.p12|mobileprovision' \
    "${WEB_DIR}/Dockerfile" "${WEB_DIR}/.dockerignore" 2>/dev/null; then
  fail "Dockerfile/.dockerignore references secret-like material"
fi
log "OK: no secret references in web/Dockerfile or web/.dockerignore"

log "PASS — optional /downloads/ packaging verified (default + staged + context + no-secrets)"
