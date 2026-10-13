# Contributing to GREENS

Contributions are welcome when they preserve compatibility, scientific provenance, and explicit evidence boundaries. By participating, follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Before opening a change

Discuss broad schema, CLI, evidence-tier, or experiment-design changes before implementation. Existing CLI behavior, default formatting, and JSON/CSV fields are compatibility contracts. Add new flags or versioned fields instead of changing their meaning.

Never rewrite frozen campaign evidence, delete negative results, promote a partial run, or replace null with zero. A new campaign receives a new ID and directory. Machine-specific paths belong only in executed provenance; reusable code uses relative paths or configuration.

## Development setup

```bash
python -m venv .venv
# activate .venv for your shell
python -m pip install -r requirements.txt
make reviewer-smoke
```

For the native build, install GNU Make and a C++17 compiler. Optional RTL/physical tools are documented in [Installation](docs/INSTALLATION.md).

## Required validation

Run from the repository root:

```bash
make
make test
python -m pytest -q
python scripts/check_artifact.py
python scripts/check_documentation.py
python scripts/reproduce_iscas.py --check
git diff --check
```

Add focused unit/regression coverage and preserve golden CLI outputs. ML code belongs under `ml/`, remains advisory, and requires deterministic training, OOD fallback, and train-to-predict smoke tests. Generated test data must use temporary directories and must not be committed.

## Add a hardware identity

Declare protection semantics and the error universe, payload/codeword mapping, interface, reset behavior, latency, initiation interval, and supported flags. Add clean/error/unsupported-mask verification, retain failures, and provide explicit alignment/formal evidence for equivalence claims. A pipeline, structural realization, macro organization, or physical-flow change creates another identity and requires its own physical evidence when physical claims are made.

## Reviewer derivations

Run `python scripts/reproduce_iscas.py --check` after changing the ISCAS analysis or navigation. Default output is ignored `tmp/reproduce-iscas/`. Refresh intentionally tracked CSV/JSON/SVG references only with a documented analysis change. Use semantic scientific identifiers in public prose and keep necessary checksums in machine-readable integrity mechanisms. Remove author filesystem, machine, branch-development, and debugging metadata from public examples.

## Evidence and reporting

Every experiment must declare identities, useful-payload functional unit, tools/PDK/PVT, workloads/fault populations, seeds, resource budget, expected artifacts, hashes, and failure semantics before execution. Retain raw reports and logs alongside normalized records. Reports, tables, and figures must trace to the evidence package; presentation does not upgrade evidence. Publication manuscripts and submission PDFs are maintained outside this source repository.

See the [Developer guide](docs/developer-guide.md), [Adding an ECC](docs/adding-an-ecc.md), [Adding an experiment](docs/adding-an-experiment.md), and [Results schema](docs/results-schema.md).

## Pull requests

Keep pull requests focused. Explain why, what changed, scientific impact, validation, reproducibility impact, reviewer-facing impact, and a checklist. Merge only after all relevant checks pass and review findings are resolved; follow protected-branch policy. Never push directly to main. Do not include local binaries, temporary renders, caches, credentials, private datasets, or unlicensed third-party material.
