# Canonical results and reproduction

| Population | Canonical record | Scope |
|---|---|---|
| Registry software study | [Framework](../../green_ecc_physical_simulation/multi_ecc_evaluation/framework_summary.json), [study summary](../../green_ecc_physical_simulation/multi_ecc_evaluation/software_study_summary.json) | Exact/analytical; physical objectives null |
| Matched 40-run population | [v3.2 manifest](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/RUN_MANIFEST.json) | Includes timing failures |
| 46 E5 logic records | [v3.3 status](../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/CAMPAIGN_STATUS.json), [manifest](../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/RUN_MANIFEST.json) | SECDED/Hsiao logic only |
| Fresh OpenRAM attempt | [Provenance](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/OPENRAM_PROVENANCE.json) | Cutoff; DRC/LVS/characterization incomplete |

Start with `make reviewer-smoke`; then `make`, `make test`, `python3 -m pytest -q`, and `python scripts/check_artifact.py`. [Evidence map](../evidence-map.md) links result tables and campaign validators.

Comparisons need hashes, seeds, clocks, operation/workload identities, tool pins, exceptions, and qualification states. EPC/carbon improvements require the actual denominator and compatible qualified population. Cleanup adds no new improvement percentage.

`make reproduce` intentionally regenerates the registry study. Full physical reruns require a new campaign identity and pinned environment; they are outside lightweight cleanup validation. Keep frozen bytes rather than resealing mismatches. External archives must have verified hashes and restoration manifests.
