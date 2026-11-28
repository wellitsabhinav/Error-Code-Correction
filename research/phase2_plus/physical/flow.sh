#!/usr/bin/env bash
set -euo pipefail

cd /OpenROAD-flow-scripts/flow
tools=/OpenROAD-flow-scripts/tools/install
openroad="${tools}/OpenROAD/bin/openroad"
yosys="${tools}/yosys/bin/yosys"
export PATH="${tools}/OpenROAD/bin:${tools}/yosys/bin:$PATH"
lib="$PWD/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
if [[ "$1" == preflight ]]; then
    "$openroad" -version
    "$yosys" -V
    "$yosys" -Q -p 'help synth'
    printf '%s  %s\n' "$2" "$lib" | sha256sum -c -
    exit
fi

arch=$1
top=$2
seed=$3
target="/campaign-run/results/sky130hd/$top/seed$seed"
set -x
make "DESIGN_CONFIG=/rev2-repo/scripts/revision2/configs/$arch.mk" \
    WORK_HOME=/campaign-run "FLOW_VARIANT=seed$seed" CLOCK_PERIOD=10.0 \
    ABC_CLOCK_PERIOD_IN_PS=10000 NUM_CORES=1 LEC_CHECK=0 \
    "OPENROAD_EXE=$openroad" "YOSYS_EXE=$yosys" \
    "GPL_RANDOM_SEED=$seed" "GRT_SEED=$seed" "OR_SEED=$seed" \
    "$target/6_final.odb" "$target/6_final.v" "$target/6_final.spef" "$target/6_final.sdc"

export P2P_RESULTS="$target" P2P_LIBERTY="$lib"
"$openroad" -exit /phase2-plus/characterize.tcl
