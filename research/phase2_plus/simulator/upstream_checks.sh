#!/usr/bin/env bash
set -euo pipefail

cd "$1"
prefix="$2"
for case in sdf_interconnect{1,2,3,4}; do
    "$prefix/bin/iverilog" -B "$prefix/lib/ivl" -Ttyp -ginterconnect -gspecify \
        -o "$case.vvp" "ivltests/$case.v" > "$case.compile.log" 2>&1
    "$prefix/bin/vvp" "$case.vvp" > "$case.runtime.log" 2>&1
    diff -u "$case-vvp-stdout.gold" "$case.runtime.log" > "$case.diff"
done
