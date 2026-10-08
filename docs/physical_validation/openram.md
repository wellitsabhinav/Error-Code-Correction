# OpenRAM status

The fresh target was 256×72, one read/write port, one bank, two words per row, TT/1.8 V/25 °C. OpenRAM 1.2.48 commit `b6a6f12642df6b84facc24a77f9a6f67a0d62dab` ran for 10,800 s and exited 137 at runtime cutoff.

Provenance retains a log and partial geometry (547.34×296.235 µm from the hierarchy log). DRC/LVS/characterization did not complete; no fresh qualified LEF/Liberty/Verilog/SPICE set was produced. Geometry is not qualification. Earlier control/diagnosis failures remain historical evidence.

Remaining requirements: consistent generated views, completed DRC/LVS/characterization, pin/bit mapping, and process/library/tool provenance. Inherited SRAM22 views are independent and do not complete this attempt. See [OpenRAM provenance](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/OPENRAM_PROVENANCE.json), [negative results](../experiments/negative_results.md), and [SRAM22](sram22.md).
