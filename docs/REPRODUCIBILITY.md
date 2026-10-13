# GREENS reproducibility

## ISCAS claim reproduction

Start with [the ISCAS artifact](../experiments/iscas/README.md). Run `python scripts/reproduce_iscas.py`, then `python scripts/reproduce_iscas.py --check`. This consumes repository-contained evidence and generates the primary cohort tables and figure without EDA tools or development-history reconstruction.

## Level 1: broader reviewer smoke path

From the repository root, in a Python 3.10–3.12 environment:

```bash
python -m pip install -r requirements.txt
make reviewer-smoke
```

Expected outcome: `ARTIFACT_CHECK_PASS`, a passing Hsiao verification report, deterministic seeded simulator JSON, and passing targeted tests. Outputs print to the terminal; no physical tool is used.

## Level 2: complete software validation

Prerequisites: Level 1 plus GNU Make and a C++17 compiler.

```bash
make
make test
python -m pytest -q
python scripts/build_documentation.py --check
```

`make` emits native binaries and object/dependency files in the repository root. They are ignored and removable with `make clean`. Pytest uses temporary directories outside the tracked fixture tree. If the platform has multiple MinGW runtimes, correct `PATH` until `python eccsim.py doctor --strict` passes.

## Level 3: campaign evidence audit or physical rerun

Audit first: read the campaign README, status, run manifest, validation results, hashes, and preserved logs. Package validation scripts may be run without allocating a new physical campaign.

A physical rerun requires the exact or explicitly migrated container/tool/PDK/library environment, sufficient storage and runtime, and a new campaign identity. Do not overwrite frozen evidence. The completed v3.3 campaign had a single 54,000-second deadline and is not resumable as a fresh budget.

## Determinism and provenance

Software workflows record fixed seeds where randomness is intentional. Evidence packages bind named inputs, tool conditions, operation definitions, and qualification states. Machine-readable integrity checks validate retained records automatically.

Exact regeneration can still differ when compiler, solver, standard-library, EDA, or PDK identities differ. Treat a changed hash as a result to investigate, not something to rewrite silently.

## Expected failure modes

- Optional RTL/EDA tools absent: relevant checks skip or remain unavailable.
- Mixed Windows compiler/runtime DLLs: native executable launch may fail; align `PATH`.
- OpenRAM timeout: the retained attempt is intentionally partial, not a failed artifact check.
- Physical run lacks macro data, activity, or signoff: retain null/block status.
- Documentation regeneration changes frozen files: review the diff and never reseal historical evidence casually.
