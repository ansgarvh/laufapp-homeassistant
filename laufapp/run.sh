#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p /data /data/tmp
cd /app

MAIN_PID=""
GATEWAY_PID=""
CLEANED_UP=0

cleanup() {
  if [[ "$CLEANED_UP" == "1" ]]; then return; fi
  CLEANED_UP=1
  if [[ -n "$MAIN_PID" ]]; then kill "$MAIN_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$GATEWAY_PID" ]]; then kill "$GATEWAY_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$MAIN_PID" ]]; then wait "$MAIN_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$GATEWAY_PID" ]]; then wait "$GATEWAY_PID" >/dev/null 2>&1 || true; fi
}

handle_signal() {
  local signal_name="$1"
  local exit_code="$2"
  echo "LAUFAPP_SHUTDOWN signal=${signal_name} main_pid=${MAIN_PID:-none} gateway_pid=${GATEWAY_PID:-none}" >&2
  cleanup
  exit "$exit_code"
}

trap cleanup EXIT
trap 'handle_signal SIGTERM 143' TERM
trap 'handle_signal SIGINT 130' INT

uvicorn main_v0212:app \
  --host 0.0.0.0 --port 8099 \
  --no-proxy-headers --no-server-header \
  --limit-concurrency 64 --timeout-keep-alive 5 &
MAIN_PID=$!
echo "LAUFAPP_PROCESS_STARTED child=main pid=$MAIN_PID port=8099 version=0.2.12" >&2

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
  echo "LAUFAPP_STARTUP_FAILED child=main pid=$MAIN_PID reason=healthcheck_timeout" >&2
  exit 1
fi

if python - <<'PY' >/dev/null 2>&1
import health_auto_export_v0212 as hae
raise SystemExit(0 if hae.token_configuration_error() is None else 1)
PY
then
  uvicorn health_auto_export_gateway:app \
    --host 0.0.0.0 --port 8100 \
    --no-proxy-headers --no-server-header \
    --limit-concurrency 8 --timeout-keep-alive 5 &
  GATEWAY_PID=$!
  echo "LAUFAPP_PROCESS_STARTED child=gateway pid=$GATEWAY_PID port=8100 version=0.2.12" >&2

  EXITED_PID=""
  set +e
  wait -n -p EXITED_PID "$MAIN_PID" "$GATEWAY_PID"
  STATUS=$?
  set -e
  if [[ "$EXITED_PID" == "$MAIN_PID" ]]; then
    EXITED_CHILD="main"
  elif [[ "$EXITED_PID" == "$GATEWAY_PID" ]]; then
    EXITED_CHILD="gateway"
  else
    EXITED_CHILD="unknown"
  fi
  echo "LAUFAPP_CHILD_EXIT child=$EXITED_CHILD pid=${EXITED_PID:-unknown} status=$STATUS action=stop_addon" >&2
else
  echo "Health Auto Export gateway disabled until a strong sync token is configured." >&2
  set +e
  wait "$MAIN_PID"
  STATUS=$?
  set -e
  echo "LAUFAPP_CHILD_EXIT child=main pid=$MAIN_PID status=$STATUS action=stop_addon" >&2
fi

cleanup
exit "$STATUS"