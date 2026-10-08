# Reproduction environment

Portable software uses Python 3.10–3.12, GNU Make, and C++17. Install `requirements.txt`; `requirements-lock.txt` records the existing lock and scikit-learn 1.7.2 is explicitly pinned. This cleanup host has Windows Python 3.12.5 and the existing MinGW UCRT64 compiler. Align compiler/runtime DLLs on PATH.

Windows `python3` can be a Store stub despite working `python`. Use `python -m pytest -q` or a session-local python3 alias to that same installed interpreter. Cleanup does not replace system installations.

WSL Ubuntu 24.04 hosts retained campaigns. Physical reproduction needs the manifest-pinned container, PDK/library, tool revisions, constraints, and storage. [ORFS](../physical_validation/orfs.md) and [OpenRAM](../physical_validation/openram.md) record current pins; per-run manifests remain authoritative.

Absolute paths in frozen records are execution provenance, not installation defaults. Generic EDA tools, PDKs, and PACT material are retained outside destructive cleanup. Missing optional tools are unavailable/skipped, not physical-validation success. See [reproduction levels](../REPRODUCIBILITY.md) and [canonical audit](canonical_results.md).
