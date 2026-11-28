#!/usr/bin/env bash
set -euo pipefail

cd "$1"
entry="$2"
shift 2
exec python3 "$entry" "$@"
