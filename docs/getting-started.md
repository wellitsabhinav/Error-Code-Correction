# Getting started with GREENS

This path produces a useful result without installing a physical-design stack.

## Prerequisites

- Git;
- Python 3.10–3.12;
- GNU Make for the convenience targets;
- internet access only for the initial dependency installation.

From a shell in the directory where you keep source repositories:

```bash
git clone https://github.com/wellitsabhinav/Error-Code-Correction.git GREENS
cd GREENS
python -m venv .venv
```

Activate the environment:

```bash
# Bash or WSL
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Install and validate:

```bash
python -m pip install -r requirements.txt
make reviewer-smoke
```

Expected terminal markers include `ARTIFACT_CHECK_PASS` and a passing pytest summary. The Hsiao verification and SRAM simulation also emit JSON. The command writes no research result into a tracked campaign directory.

## What just happened?

The smoke workflow checked required public files, parsed canonical manifests and CSV files, verified that global-winner and whole-memory-E5 guards remain closed, checked public documentation links, verified one registered implementation, ran 100 seeded SRAM iterations, and executed representative tests.

## Inspect and change the ECC

List registered codes:

```bash
python eccsim.py ecc list
```

Inspect one mathematical code and its implementations:

```bash
python eccsim.py ecc inspect --code hsiao-secded-72-64-v1
python eccsim.py ecc implementations --code extended-hamming-secded-72-64-v1
```

Run a different small SRAM model by changing `--scheme`, `--size-kb`, `--word-bits`, `--iterations`, or `--seed` within the choices shown by:

```bash
python eccsim.py sram simulate --help
```

The SRAM CLI prints JSON with `--json`; add `--out-csv PATH` only when you intentionally want a file. Legacy SRAM scheme names are not automatically identical to versioned registry implementation IDs; use [ECC architectures](ecc-architectures.md) for the distinction.

## Next steps

- Build and run the full software suite: `make`, `make test`, `python -m pytest -q`.
- Compare candidates using [User guide](user-guide.md).
- Understand claim boundaries in [Evidence model](evidence-model.md).
- Reproduce a software study or audit campaign evidence using [Reproducibility](REPRODUCIBILITY.md).
- Prepare physical tools using [Installation](INSTALLATION.md) and [Physical design](physical-design.md).
