#!/usr/bin/env bash
set -euo pipefail

tools=/OpenROAD-flow-scripts/tools/install
export P2P_LIBERTY=/OpenROAD-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
if [[ "$1" == library ]]; then
    "$tools/yosys/bin/yosys" -Q -p "read_liberty -ignore_miss_func $P2P_LIBERTY; write_verilog -noattr /campaign-run/functional.v"
else
    export P2P_SCOPE="$1"
    "$tools/OpenROAD/bin/openroad" -exit /phase2-plus/zero_power.tcl
fi
