# Reproduce GREENS ISCAS claims from frozen evidence

This workflow verifies and derives the supplied headline claim set. It does not regenerate RTL-to-GDS, install a PDK, or require a C++ compiler. The manuscript PDF/source is outside the repository; original publication numbering/layout cannot be checked here.

## Environment and clone

Use Python 3.10–3.12. This claim-reproduction command consumes repository-contained files and needs no development branches or historical checkout. The repository retains substantial physical evidence (about 11.1 GB of uncompressed tracked files in the original inventory), so allow sufficient disk space.

```bash
git -c core.longpaths=true clone --depth 1 https://github.com/wellitsabhinav/Error-Code-Correction.git GREENS
cd GREENS
git config core.longpaths true
python -m venv .venv
# Bash/WSL: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The clone command supports retained long paths without changing global settings. Git attributes preserve the exact campaign bytes. Do not bulk-normalize or reseal evidence. Full historical development validators separately require complete Git history and the authorized mixed-newline restoration helper; neither is needed for this claim command.

## Exact commands

Run from the root:

```bash
python scripts/reproduce_iscas.py
python scripts/reproduce_iscas.py --check
```

Equivalent analysis target: `make reproduce-iscas`. To intentionally refresh reviewer derivations after a documented analysis change:

```bash
python scripts/reproduce_iscas.py --output experiments/iscas/generated
```

Frozen campaigns are read-only inputs to this entry point. Its default output is ignored `tmp/reproduce-iscas/`; `experiments/iscas/generated/` intentionally tracks small reviewer derivations. `--check` uses a temporary directory and compares CSV/JSON bytes; SVG styling is excluded from byte comparison because plotting-library versions may differ.

## Expected outputs

| File | Meaning |
|---|---|
| `headline_results.json` | Seeds [13,17,19,23], 4 pairs, 20 cells, 40 records, Hsiao lower 4, BCH feasible 0/5; lifecycle winner null |
| `cohort_admission.csv` | Ten executed runs; explicit setup/hold and operation-completeness reasons |
| `primary_operation_pairs.csv` | 20 matched deltas, units, semantic record IDs, repository-relative source paths |
| `operation_summary.csv` | Five operation summaries over four primary seeds |
| `bch_setup_feasibility.csv` | Five 10 ns BCH setup observations; negative results retained |
| `workload_read_write_slice.csv` | Per-seed weighted energy at clean-read fractions 0–1; other operation weights zero |
| `campaign_conditions.json` | Human-readable scientific population and tool conditions |
| `integrity/` | Automatic input-integrity checks and exact external tool pins |
| `operation_and_workload.svg` | Operation deltas and the two-operation workload slice |

Both commands print `status: PASS` only after checking the v3.3 seal, raw collector/manifest agreement, parent identity, BCH report hashes, energy normalization, matched operation controls, and expected headline counts. Missing or changed evidence yields a nonzero exit and a reason. The 1,697 seal entries are verified evidence files, not independent experiments.

## Interpret the outputs

Negative Hsiao-minus-Extended-Hamming energy favors Hsiao within the ECC-logic boundary. Three of four clean-read cells and one idle cell are negative. Write, correction, and detection cells are positive in this primary cohort. Weighted slices describe operation mixes; they do not infer physical fault rates, memory access distributions, or whole-system energy.

The 46/23 historical aggregate includes six read records from seed 11. Its Hsiao hold failure and incomplete idle/write activity exclude that pair from primary decisions. The historical setup-only `timing_feasible` flag is preserved.

## Additional inexpensive checks

```bash
python scripts/check_artifact.py
python -m pytest -q tests/python/test_iscas_reproduction.py
```

The full software/native contract is in [CONTRIBUTING.md](../../CONTRIBUTING.md). [Physical regeneration](regeneration.md) needs a new campaign identity and pinned environment. Do not run frozen `build_campaign.py` as a reviewer shortcut: it writes inside the campaign.

For a hash mismatch, confirm clone attributes and the authorized restoration helper. If bytes still disagree, stop and report the mismatch; never change the declared hash to force a pass. [Environment](../../docs/reproduction/environment.md) · [Troubleshooting](../../docs/TROUBLESHOOTING.md)
