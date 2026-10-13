# GREENS maintained dependencies

The supported analysis/development environment uses Python 3.10–3.12 and the exact direct and transitive versions in [requirements-lock.txt](../../requirements-lock.txt). [requirements.txt](../../requirements.txt) imports that lock, so the ordinary installation command and CI use the same definitions.

```bash
python -m venv .venv
# activate .venv for your shell
python -m pip install -r requirements.txt
python -m pip check
```

## Compatibility decisions

The October 2026 audit checked stable, non-yanked PyPI releases and their Python requirements. All 32 selected packages are the newest stable releases compatible with every supported interpreter and the dependency solver. NumPy, SciPy, pandas, Matplotlib and scikit-learn have newer releases requiring newer Python versions; preserving Python 3.10 support is intentional. No prerelease is selected. [Per-package audit](dependency-audit.csv) records previous pins, latest stable releases, compatible releases, selected pins, roles and primary sources.

The maintained native build requires GNU Make and a C++17 compiler. CMake now requires 3.16 or later to support GoogleTest 1.18.0. Its stable archive and checksum replace the moving main-branch download. Linux CI installs CMake 4.4.4, then configures, builds and runs the CMake unit-test contract.

GitHub Actions use exact stable release tags: checkout 7.0.1, setup-python 7.0.0, upload-artifact 7.0.2, and setup-msys2 2.33.0. Hosted runners supply their supported runtimes. [Automation audit](automation-toolchain-audit.csv) records these decisions and the separately retained physical-tool boundary. [External-tool release inventory](external-tool-releases.csv) records current upstream release channels; their latest tags do not override frozen physical-tool identities.

## Frozen scientific environments

Campaign-specific OpenRAM Python locks, containers, ORFS/OpenROAD/OpenSTA/Yosys revisions, PDK/library views and legacy EDA environments are immutable scientific conditions. They are not the maintained installation requirements. A tool upgrade creates a new experiment identity and requires new evidence; it cannot redefine a completed measurement.

The audit found seven alerts in the previous maintained lockfile; the selected pytest and pypdf versions exceed every listed patched version. Other reported alerts belong to historical OpenRAM/recovered environment records. Those records are retained verbatim and are excluded from dependency-update automation.

## Validation and updates

The candidate environment passes dependency consistency checks and both CTest executables pass. With MinGW on Windows, use matching runtime DLLs on PATH or configure `-DCMAKE_EXE_LINKER_FLAGS="-static-libgcc -static-libstdc++"`. Regenerating all 24 existing documentation figure-data files produces no numerical differences; the 17 original rendered figures and their integrity records remain retained. Cross-platform tests compare regenerated aggregate statistics with a relative tolerance of 1e-14 for final-bit platform variation, while identities, classifications, integer counts, missing values and frozen input bytes stay strict.

[CI](../../.github/workflows/ci.yml) tests Python 3.10, 3.11 and 3.12 on Linux and Python 3.11 with UCRT64 on Windows, including native builds, the complete Python suite and golden CLI contracts. Fast push/PR checks cover public quality, software/native smoke and supported SECDED RTL. Frozen campaign tests regenerate in disposable copies.

Dependabot reviews maintained root Python definitions and GitHub Actions weekly. It does not update frozen nested environment records. Every dependency PR must pass compatibility and numerical reproduction checks before merging; no automatic merge is configured.
