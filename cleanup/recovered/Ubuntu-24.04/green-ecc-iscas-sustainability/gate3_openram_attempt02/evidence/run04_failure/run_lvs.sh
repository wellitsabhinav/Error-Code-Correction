#!/bin/sh
export OPENRAM_TECH="/attempt/source/OpenRAM/technology:/attempt/source/OpenRAM/compiler/../technology"
echo "$(date): Starting LVS using Netgen /usr/local/bin/netgen"
/usr/local/bin/netgen -noconsole << EOF
lvs {sky130_sram_1rw_72x256_gate3a02.spice sky130_sram_1rw_72x256_gate3a02} {sky130_sram_1rw_72x256_gate3a02.sp sky130_sram_1rw_72x256_gate3a02} setup.tcl sky130_sram_1rw_72x256_gate3a02.lvs.report -full -json
quit
EOF
magic_retcode=$?
echo "$(date): Finished ($magic_retcode) LVS using Netgen /usr/local/bin/netgen"
exit $magic_retcode
