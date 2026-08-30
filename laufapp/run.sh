#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p /data /data/tmp
cd /app

uvicorn health_auto_export_gateway:app --host 0.0.0.0 --port 8100 --proxy-headers --forwarded-allow-ips='*' &
GATEWAY_PID=$!
uvicorn main_v026:app --host 0.0.0.0 --port 8099 --proxy-headers --forwarded-allow-ips='*' &
MAIN_PID=$!

cleanup() {
  kill "$MAIN_PID" "$GATEWAY_PID" >/dev/null 2>&1 || true
  wait "$MAIN_PID" "$GATEWAY_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT TERM INT

wait -n "$MAIN_PID" "$GATEWAY_PID"
STATUS=$?
cleanup
exit "$STATUS"
