# GREENS frozen scientific evidence

The scientific dataset is identified by protection service, architecture, technology, target period, physical seed, and operation. No author filesystem, development branch, or historical checkout is needed for reproduction.

| Scientific object | Public data |
|---|---|
| Experiment conditions and tools | [campaign_conditions.json](../generated/campaign_conditions.json) |
| Route/setup/hold and operation admission | [cohort_admission.csv](../generated/cohort_admission.csv) |
| Primary matched ECC-logic energies | [primary_operation_pairs.csv](../generated/primary_operation_pairs.csv) |
| Operation-specific preference | [operation_summary.csv](../generated/operation_summary.csv) |
| Evaluated BCH setup feasibility | [bch_setup_feasibility.csv](../generated/bch_setup_feasibility.csv) |
| Workload decision slice | [workload_read_write_slice.csv](../generated/workload_read_write_slice.csv) |

These small tables are reproducible projections of immutable execution records. They carry scientific values and repository-relative source pointers; source datasets are not relocated or altered. [Reproduce](../reproduction.md) · [Claim map](../claims.md)

<details>
<summary>Low-level integrity and original execution records</summary>

The command validates machine-readable integrity automatically. [Integrity inputs](../generated/integrity/) contain checksums and external tool pins, with no author filesystem paths. Checksums are not scientific results and need not be read to understand the paper.

The original [activity campaign](../../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/) and [matched physical campaign](../../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/) retain historical executed provenance. Some immutable records contain original execution locations or development identifiers. They are retained where required by evidence integrity and are not installation instructions. The public reproduction interface resolves repository-contained inputs automatically.

</details>
