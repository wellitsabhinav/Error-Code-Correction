# GREENS evidence map

The [ISCAS claim map](../experiments/iscas/claims.md) and [public scientific evidence](../experiments/iscas/evidence/README.md) provide the reviewer path for the primary decision cohort. The table below covers broader retained research.

This page connects the repository's main result classes to inspectable evidence and maintained validation commands. It does not assign publication figure or table numbers, and it does not upgrade the qualification of any source quantity.

| Result class | Primary evidence | Validation or inspection |
|---|---|---|
| Code and implementation identities | `green_ecc_physical_simulation/registry/` and the generated [ECC catalogue](ECC_CATALOGUE.md) | `python eccsim.py ecc list`; `python eccsim.py ecc verify --implementation ID` |
| Conditional logical reliability | `campaigns/iscas_sustainability_extension/green_matrix_v3_2/data/` | `make artifact-check` and campaign-local validators |
| Matched physical population | [Physical run results](../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/PHYSICAL_RUN_RESULTS.csv) and [final report](../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/FINAL_REPORT.md) | Inspect the run manifest and hashes; use the Level 3 environment for a rerun |
| Fresh OpenRAM attempt | [OpenRAM provenance](../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/OPENRAM_PROVENANCE.json) | Confirm timeout, exit state, and incomplete DRC/LVS/characterization |
| Activity-qualified ECC-logic observations | [v3.3 campaign status](../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/CAMPAIGN_STATUS.json) and its additive matrix | `make artifact-check`; inspect package validation records |
| Activity-energy study data | [Evidence package](../campaigns/date_2027_activity_qualified_ecc_energy_rev2/README.md), source data, figures, tables, and provenance manifest | Run `python scripts/build_artifacts.py` inside that package when intentionally regenerating derived artifacts |
| Global-winner and lifecycle limits | [Limitations](limitations.md), [evidence model](evidence-model.md), and campaign status fields | Confirm `NO_GLOBAL_WINNER_QUALIFIED` and the blocked operands |

## Qualification rules

- A mathematical proof, logical simulation, structural synthesis result, physical measurement, and lifecycle model are different evidence classes.
- Missing values remain null or blocked; they are never silently replaced with zero.
- Negative, partial, and timed-out results remain visible when they define a claim boundary.
- A figure, summary table, or report cannot raise the evidence tier of its inputs.

## Publication boundary

Publication manuscripts, peer-review notes, and submission PDFs are maintained outside this software repository. Reusable experiment code, normalized data, figures, reports, and provenance records remain here so software and scientific claims can be audited independently.
