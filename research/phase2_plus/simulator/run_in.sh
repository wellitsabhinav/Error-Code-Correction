#!/usr/bin/env bash
set -euo pipefail
cd "$1"
shift
exec "$@"
