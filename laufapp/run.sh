#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p /data /data/tmp
cd /app
exec uvicorn main_v022:app --host 0.0.0.0 --port 8099 --proxy-headers --forwarded-allow-ips='*'
