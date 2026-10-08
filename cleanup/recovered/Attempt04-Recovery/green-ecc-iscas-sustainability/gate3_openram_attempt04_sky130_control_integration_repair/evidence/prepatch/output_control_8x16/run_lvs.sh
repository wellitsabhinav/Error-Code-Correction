#!/bin/sh
export OPENRAM_TECH="/attempt/source/OpenRAM/technology:/attempt/source/OpenRAM/compiler/../technology"
echo "$(date): Starting LVS using Netgen /usr/local/bin/netgen"
/usr/local/bin/netgen -noconsole << EOF
lvs {sky130_sram_1rw_8x16_gate3a03_control.spice sky130_sram_1rw_8x16_gate3a03_control} {sky130_sram_1rw_8x16_gate3a03_control.lvs.sp sky130_sram_1rw_8x16_gate3a03_control} setup.tcl sky130_sram_1rw_8x16_gate3a03_control.lvs.report -full -json
quit
EOF
magic_retcode=$?
echo "$(date): Finished ($magic_retcode) LVS using Netgen /usr/local/bin/netgen"
exit $magic_retcode
