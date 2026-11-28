#!/usr/bin/env bash
set -euo pipefail

dpkg -i /tool-inputs/deb/*.deb
mkdir -p /tmp/phase2-plus-iverilog
tar -xzf /tool-inputs/iverilog-v13_0.tar.gz -C /tmp/phase2-plus-iverilog --strip-components=1
cd /tmp/phase2-plus-iverilog
cp COPYING /campaign-run/upstream-license.txt
sh autoconf.sh
./configure --prefix=/campaign-run/icarus13 CFLAGS=-O2 CXXFLAGS=-O2
make -j1
make -j1 install

installed=/campaign-run/icarus13
mkdir -p /campaign-run/upstream-checks
grep -nE 'TIMINGCHECK not supported|COND not supported|interconnect_delay' vpi/sdf_parse.y \
    > /campaign-run/upstream-checks/source-limits.txt
cp ivtest/ivltests/sdf_interconnect{1,2,3,4}.{v,sdf} /campaign-run/upstream-checks/
cp ivtest/gold/sdf_interconnect{1,2,3,4}-vvp-stdout.gold /campaign-run/upstream-checks/
"$installed/bin/iverilog" -V > /campaign-run/icarus-version.log 2>&1
