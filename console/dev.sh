#!/usr/bin/env bash
set -euo pipefail

node server.mjs &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

npm run dev:frontend -- "$@"
