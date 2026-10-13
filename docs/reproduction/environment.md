# GREENS reproduction environment

The ISCAS claim workflow requires Python 3.10–3.12 and repository-contained frozen evidence. Install `requirements.txt`; it imports the exact maintained dependency lock, including interpreter-conditional packages. [Dependency compatibility audit](../maintenance/dependencies.md) explains the selected versions. [Exact ISCAS commands](../../experiments/iscas/reproduction.md) use no EDA tools, native compiler, development branch, or historical checkout.

The broader software/native suite additionally requires GNU Make and a C++17 compiler. On Windows, select a consistent compiler/runtime on PATH and use the installed Python interpreter. Place optional Icarus, Verilator, and Yosys executables on PATH or configure `GREENS_TOOL_BIN` for the maintained validation runners.

Physical regeneration requires Linux or a compatible Linux container environment, the retained ORFS/OpenROAD tool conditions, PDK/library/macros, constraints, and sufficient resources. [Physical regeneration](../../experiments/iscas/regeneration.md) separates that procedure from claim reproduction.

Git attributes preserve campaign byte representations. For the full historical development validators, run `python scripts/restore_frozen_checkout_bytes.py --restore --refresh-index` for authorized historical byte restoration. Do not bulk-convert or reseal evidence. Those comprehensive historical validators require complete Git history; neither the helper nor historical ancestry is needed by the ISCAS claim entry point.

Missing optional tools remain unavailable/skipped, never validation success. [Troubleshooting](../TROUBLESHOOTING.md) · [Reproduction levels](../REPRODUCIBILITY.md)
