# Negative and blocked results

| Finding | Evidence | Implication |
|---|---|---|
| SEC-DAEC counterexample | [ECC status](../ecc-architectures.md) | Excluded from matched comparison |
| Historical cyclic (63,51) distance 2 | [Catalogue](../ECC_CATALOGUE.md) | Cannot inherit primitive-BCH guarantees |
| OpenRAM timeout / exit 137 | [Provenance](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/OPENRAM_PROVENANCE.json) | No qualified fresh macro; DRC/LVS/characterization incomplete |
| Timing failures | [Matched manifest](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/RUN_MANIFEST.json) | BCH fails both targets; SECDED/Hsiao fail 5 ns |
| Incomplete macro energy/activity | [v3.3 status](../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/CAMPAIGN_STATUS.json) | E5 logic is not whole-memory energy |
| Missing beam/fluence/Qcrit and map | Same status; [reliability](../reliability-model.md) | Absolute physical FIT and interleaver reliability blocked |
| Missing SKY130 inventory/yield/lifetime | Same status; [sustainability](../sustainability-model.md) | Lifecycle carbon/global ranking blocked |

Failed runs may be compressed after unique source/configs and compact summaries are published and archives verified. Decisive logs, manifests, seeds, tool pins, constraints, and block/null states remain discoverable. Cleanup changes no evidence ceiling.


Cleanup CI replay also exposed a failing legacy generic `asic/rtl/bch/bch_codec.sv` BCH(63,51) example: its bench fails double-bit correction before reaching the expected triple-collision test. This code is distinct from the verified primitive software and shortened BCH(78,64) registry artifacts. See [the recorded replay](../../cleanup/BCH_RTL_CI_NEGATIVE_RESULT.json). Cleanup preserves this negative result and does not repair or qualify that legacy RTL.
