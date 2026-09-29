#!/bin/sh
# NerveCenter Web container entrypoint (nginx:1.27-alpine).
#
# Renders /etc/nginx/nginx.conf.template -> /etc/nginx/nginx.conf with a
# SCOPED envsubst (only the variables we care about), so nginx runtime
# variables ($host, $uri, ...) survive. The official image's template
# mechanism renders /etc/nginx/templates/* into /etc/nginx/conf.d/ (http
# context only), which cannot host a full main config — hence this entrypoint.
set -eu

TEMPLATE=/etc/nginx/nginx.conf.template
TARGET=/etc/nginx/nginx.conf

: "${API_UPSTREAM:=api.nervecenter.svc}"
: "${API_PORT:=8000}"

envsubst '${API_UPSTREAM} ${API_PORT}' < "$TEMPLATE" > "$TARGET"
nginx -t

exec nginx -g 'daemon off;'
