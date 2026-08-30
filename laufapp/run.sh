#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p /data /data/tmp
cd /app

MAIN_PID=""
GATEWAY_PID=""

cleanup() {
  if [[ -n "$MAIN_PID" ]]; then kill "$MAIN_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$GATEWAY_PID" ]]; then kill "$GATEWAY_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$MAIN_PID" ]]; then wait "$MAIN_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$GATEWAY_PID" ]]; then wait "$GATEWAY_PID" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT TERM INT

# Do not trust X-Forwarded-* from arbitrary clients. In production the strict
# middleware authorizes the real TCP peer 172.30.32.2 for Home Assistant Ingress.
uvicorn main_v027:app \
  --host 0.0.0.0 --port 8099 \
  --no-proxy-headers --no-server-header \
  --limit-concurrency 64 --timeout-keep-alive 5 &
MAIN_PID=$!

# Start the externally optional gateway only after the main app completed its
# lifespan startup (database migration/init and background job recovery).
READY=0
for _ in $(seq 1 60); do
  if python - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen('http://127.0.0.1:8099/api/health', timeout=1).read()
PY
  then
    READY=1
    break
  fi
  if ! kill -0 "$MAIN_PID" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
if [[ "$READY" != "1" ]]; then
  echo "Laufapp main process did not become ready; refusing to start sync gateway." >&2
  exit 1
fi

uvicorn health_auto_export_gateway:app \
  --host 0.0.0.0 --port 8100 \
  --no-proxy-headers --no-server-header \
  --limit-concurrency 8 --timeout-keep-alive 5 &
GATEWAY_PID=$!

wait -n "$MAIN_PID" "$GATEWAY_PID"
STATUS=$?
cleanup
exit "$STATUS"
