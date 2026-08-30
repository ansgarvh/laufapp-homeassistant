#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p /data /data/tmp
cd /app

uvicorn health_auto_export_gateway:app --host 0.0.0.0 --port 8100 --proxy-headers --forwarded-allow-ips='*' &
GATEWAY_PID=$!
trap 'kill "$GATEWAY_PID" >/dev/null 2>&1 || true' EXIT TERM INT

exec uvicorn main_v026:app --host 0.0.0.0 --port 8099 --proxy-headers --forwarded-allow-ips='*'
