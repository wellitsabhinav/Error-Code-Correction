# Physical-design flow

## Recorded flow

The matched v3.2 campaign binds RTL/wrappers, constraints, tool image and commits, SKY130HD libraries, inherited SRAM22 macros, TT/25 °C/1.8 V, clocks of 10 ns and 5 ns, and seeds 11, 13, 17, 19, and 23. It contains 40 inherited runs across U0, SECDED, Hsiao SECDED, and BCH(78,64,t=2). The additive v3.3 campaign adds ten fresh 10 ns SECDED/Hsiao runs.

The authoritative entry points are the [matched campaign README](../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/README.md), [run manifest](../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/RUN_MANIFEST.json), and [v3.3 status](../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/CAMPAIGN_STATUS.json).

## Statuses are independent

- RTL-to-GDS completion means the scripted flow emitted its terminal artifact.
- Timing feasibility requires the declared setup/hold checks at the target clock.
- DRC and LVS have their own completion/pass states.
- Signoff requires the designated signoff engines and corners; a routed database alone is not signoff.
- E4 vectorless power and E5 activity-qualified power are different evidence.

Failed timing points and partial jobs are retained. In the inherited population, U0, SECDED, and Hsiao are feasible at 10 ns; only U0 is feasible at 5 ns.

## Activity-qualified logic

The v3.3 package holds 46 E5 ECC-logic records over `IDLE`, `WRITE_CLEAN`, `READ_CLEAN`, `READ_SINGLE_BIT_ERROR_CORRECT`, and `READ_DOUBLE_BIT_ERROR_DETECT`. Four seeds contain all five operations; seed 11 contains the three read operations. Functional-logic coverage is about 99.30–99.36%, minimum combinational coverage is 99.2355%, sequential coverage is 100%, and all 72 required macro output roots are annotated.

SRAM macro-internal activity and energy remain incomplete, so these records are not whole-memory E5.

## Fresh OpenRAM attempt

The fresh target was 256 words × 72 bits, one read/write port, one bank, two words per row, TT/1.8 V/25 °C. OpenRAM 1.2.48 ran for 10,800 seconds and exited 137. A compiler log and partial geometry were recorded; fresh LEF, Liberty, Verilog, SPICE, completed DRC/LVS, and characterization were not produced. Inherited SRAM22 macros are separate evidence and must not be described as fresh OpenRAM output.

## Reproduction policy

The v3.3 queue consumed 23,874.583 seconds of one 54,000-second campaign-wide budget and completed without hitting its deadline. It is a completed additive campaign, not a queue to restart. New physical experiments need a new campaign ID, output root, contract, and budget; follow [Adding an experiment](adding-an-experiment.md).
