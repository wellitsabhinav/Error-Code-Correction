# GREENS repository instructions

## Repository mission

GREENS is evidence-qualified silicon research for memory ECC hardware. Make protection service, RTL identity, physical feasibility, operation energy, and claim boundaries inspectable. Researcher: Abhinav Choudhary, ORCID https://orcid.org/0009-0001-4892-5438; IIIT-Delhi, VICAS Lab, under Dr. Anuj Grover's guidance. Preserve historical source/campaign identifiers.

## Scientific invariants

- Never mix evidence from different RTL, macro, tool, PVT, seed, constraint, workload, or lifecycle identities.
- Missing measurements stay unavailable/null; never repair them from another implementation or replace them with zero.
- Preserve failed, partial, excluded, and infeasible results when they define scientific boundaries.
- A new physical implementation is a new evidence identity. Do not infer family-wide winners from one RTL result.
- Distinguish post-route tool results from silicon measurement, signed-slack estimates from measured Fmax, and ECC-logic energy from whole-memory energy.
- Apply route, setup, and hold gates directly. Historical setup-only flags do not establish hold feasibility.

## Repository layout

Use [docs/README.md](docs/README.md) and [experiments/iscas/README.md](experiments/iscas/README.md). Existing source/flow/campaign paths are compatibility and provenance interfaces; do not move them for appearance alone. Search every consumer before a path migration. Scope-specific contracts remain authoritative for their experiments.

## Frozen evidence rules

Do not silently modify or reseal frozen campaigns, manifests, hashes, submitted snapshots, or negative results. Keep original paths and mixed byte/newline representations. The documented `scripts/restore_frozen_checkout_bytes.py` restores authorized historical bytes; it does not authorize arbitrary evidence repair. A conflicting source/hash is a validation failure.

## Reproducibility rules

Paper-level reproduction reads frozen evidence and writes separate derivations. Complete RTL-to-GDS regeneration is a different workflow. Prefer `python scripts/reproduce_iscas.py --check` for ISCAS claims. Do not run campaign builders against frozen directories during documentation validation. Do not restart the completed v3.3 queue with a renewed budget.

## RTL / HDL changes

Do not redesign RTL during presentation cleanup. For a new implementation, declare service/error universe, codeword layout, transaction interface, latency, initiation interval, reset behavior, source/configuration hashes, and a new identity. Reusing semantics does not authorize reusing physical measurements.

## Verification and formal requirements

Keep exact correctness evidence within its declared universe. Exercise clean, correction, detection, unsupported masks, interface and reset behavior as applicable. Equivalence claims need explicit alignment and formal/verification collateral. Retain counterexamples and failures. Do not describe an unexecuted proof or smoke test as passed.

## Physical-design experiments

Declare tools/container, PDK/library/macros, PVT, clock/SDC, seeds, organization, exceptions, activity/window/count, output hashes, and resource budget before execution. Record route, setup and hold separately. Preserve flow exceptions and unresolved DRC/LVS/signoff boundaries. New experiments use new directories and deadlines.

## Paper artifacts

ISCAS is the main paper-specific reviewer path. Never fabricate acceptance, DOI, or publication metadata. Keep manuscript/submission PDFs outside the repository. Review anonymity must be cleared before adding new venue-specific manuscript associations; technical evidence can remain documented. Preserve real paper titles and frozen historical names.

## Generated files

Track only intentional, reproducible tables/figures with source provenance. Write scratch analysis to `tmp/` or temporary directories. Ignore caches/native builds; do not delete campaign logs, databases, waveforms, or executables solely by extension. Update generation inputs when active public prose changes.

## Compatibility and advisory ML

Backward compatibility is mandatory. Prefer additive changes. Behavior/schema changes require explicit new flags; do not rename JSON/CSV fields or change default CLI output formatting. Add golden coverage for existing CLI outputs when changing their implementation. All ML code belongs under `ml/`; keep the existing selector as baseline and ML advisory-only. ML changes require deterministic training, OOD fallback, and train-to-predict smoke coverage.

## How to add a new experiment

Follow [docs/adding-an-experiment.md](docs/adding-an-experiment.md). Freeze contracts and identities, add meaningful correctness checks, retain raw failures and measurements, emit records with units, document eligibility/exclusions, and map claims to derivations. Do not borrow operands across boundaries.

## Validation before commit

Run from the root: `make`, `make test`, `python3 -m pytest -q` (or the same installed interpreter as `python -m pytest -q`), `python scripts/check_artifact.py`, `python scripts/reproduce_iscas.py --check`, `python scripts/check_documentation.py`, and `git diff --check`. Run relevant inexpensive HDL smoke checks when applicable; disclose unavailable checks. Review generated mutations, restore only known test output changes, and verify frozen scientific files are absent from the intended diff. Use a dedicated branch and focused pull requests. Follow branch protection; when the user authorizes merging, merge only after every relevant check passes and review findings are resolved. Never push directly to main.
