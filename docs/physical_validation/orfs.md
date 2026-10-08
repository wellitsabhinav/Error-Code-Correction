# OpenROAD / ORFS validation

The matched v3.2 manifest binds 40 runs over U0, SECDED, Hsiao SECDED, and BCH(78,64,t=2), clocks 10 ns/5 ns, and seeds 11,13,17,19,23. Conditions are SKY130HD TT/25 °C/1.8 V with inherited SRAM22 views. OpenROAD commit `ab6fd26351dc449e69059684dc6aa9ae9046eb36` and ORFS commit `56496f3980fb6e9e58f10c8aea4a98949c0fe5f2` are recorded per run with a pinned container.

At 10 ns U0/SECDED/Hsiao are feasible; at 5 ns only U0 is feasible. BCH fails both targets as implemented. A documented common SRAM22 max-transition resize-stage bypass applies across matched points; final DRVs remain visible. It is not a signoff/compliance waiver.

V3.3 adds ten fresh feasible 10 ns SECDED/Hsiao runs and 46 E5 records. Activity uses zero-delay routed-netlist simulation. Functional-logic coverage is about 99.30–99.36%; sequential coverage is 100%; 72 required macro output roots are annotated. Macro-internal energy is incomplete, so whole-memory E5 remains false.

[Physical design](../physical-design.md) separates routing, timing, DRC/LVS, and signoff. [Matched manifest](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/RUN_MANIFEST.json) contains commands/hashes/exceptions; [v3.3 status](../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/CAMPAIGN_STATUS.json) defines later scope. Do not restart a frozen queue during cleanup.
