# Installation

## Portable software environment

The recorded portable range is Python 3.10–3.12. GNU Make and a C++17 compiler are needed for the native build and full tests, but not for registry inspection.

```bash
python -m venv .venv
# activate .venv for your shell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python eccsim.py doctor --json
```

`requirements.txt` is the supported declaration. `requirements-lock.txt` records the exact packages used for the September 2026 local artifact validation.

On Windows, keep `g++` and its runtime DLLs from the same MSYS2/MinGW installation at the front of `PATH`. The doctor reports detected runtime-order mismatches.

## Physical-flow prerequisites

Physical reproduction is optional, expensive, and not installed by the Python setup. Historical campaigns record their exact tool and image identities. A new environment normally supplies `ORFS_ROOT`, `OPENROAD_HOME`, `OPENRAM_HOME`, and `PDK_ROOT` through its own controller or configuration.

The matched campaign used the retained ORFS environment, OpenROAD 26Q3-1080, OpenSTA 3.1.0, Yosys 0.68+post, SKY130HD, and inherited SRAM22 macros at TT/25 °C/1.8 V. The [run manifest](../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/RUN_MANIFEST.json) is authoritative.

Historical absolute paths are retained inside executed manifests because they are provenance. Current public software entry points use repository-relative paths; do not edit historical records to make a new machine appear identical.

## Check the installation

```bash
python eccsim.py --version
python eccsim.py doctor --json
make reviewer-smoke
```

Optional physical tools may be absent while software-only workflows remain usable. `doctor --strict` is the command to require every required local check to pass.
