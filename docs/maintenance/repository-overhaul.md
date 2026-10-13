# GREENS repository organization and public-artifact audit

## Before and after

The audited repository contained 11,429 tracked files (about 11.1 GB uncompressed): codec/software sources, verification, 8,917 campaign files, 705 documentation files, physical databases, negative results, and archival collateral. Its existing root identity already used GREENS, but attribution, citation metadata, reviewer navigation, and the primary timing-qualified cohort were incomplete or obscured by broader historical aggregates.

The public layer now presents a named research artifact with an immediate ISCAS reviewer path, scientific conditions, explicit admission/exclusions, executable claim derivations, and readable result tables. Existing source and immutable evidence locations are preserved. No large dataset is duplicated.

## Public structure

| Path | Purpose |
|---|---|
| `README.md`, `CITATION.cff`, `CONTRIBUTING.md`, `AGENTS.md` | Public mission, attribution, citation, contribution and scientific invariants |
| `docs/` | Project overview, methods, architecture, results, research-output policy and limitations |
| `experiments/iscas/` | Artifact landing page, claim index, reproduction, separate regeneration and semantic evidence index |
| `experiments/iscas/generated/` | Intentionally tracked small scientific derivations |
| `experiments/iscas/generated/integrity/` | Required automatic integrity and exact external tool pins; no author filesystem data |
| Existing `asic/`, `rtl/`, `scripts/`, `tests/`, registry/model directories | Compatible source and verification interfaces |
| Existing `campaigns/`, retained formal evidence, `reports/`, `archives/`, `cleanup/` | Frozen scientific evidence and archival provenance |

## Dependency and retention decisions

Every tracked file was inventoried by path, type, size and source identity before edits. Script/configuration/document text was searched for path consumers. Campaign manifests, analysis modules, flow configurations, macros, formal inputs, and publication-support outputs were examined as dependency groups. The full per-file working inventory remains an audit aid, not a public development log.

No scientific file or directory was moved. Campaigns and formal records bind source paths and byte representations; generation scripts and tests consume established root/guide paths. A navigation layer improves organization without changing these interfaces. Existing compatibility guide paths remain working.

No tracked evidence file was removed. Logs, databases, waveforms, failures and campaign executables can be scientific evidence, so extension-based deletion was rejected. Existing caches/build products are ignored; new scratch analysis uses `tmp/`, and documentation-tool dependencies are ignored. An obsolete untracked copy of the new integrity summary was removed after placing it under the dedicated integrity directory.

## AGENTS consolidation

Recursive case-insensitive inspection found one instruction file and no nested duplicates or conflicting agent files. Its useful instructions remain in the expanded root [AGENTS.md](../../AGENTS.md).

| Old path / instructions | Disposition | Root section |
|---|---|---|
| `AGENTS.md`: backward compatibility; additive changes; new flags for behavior/schema changes | Preserved | Compatibility and advisory ML |
| `AGENTS.md`: JSON/CSV names and default CLI formatting stable | Preserved | Compatibility and advisory ML |
| `AGENTS.md`: all ML under `ml/`; baseline selector; advisory only | Preserved | Compatibility and advisory ML |
| `AGENTS.md`: golden CLI coverage; deterministic ML, OOD fallback, train-to-predict smoke | Preserved | Compatibility and advisory ML |
| `AGENTS.md`: `make`, `make test`, complete pytest command | Preserved; equivalent interpreter spelling documented | Validation before commit |
| Nested instruction files | None found; none removed or retained | Repository layout |

Frozen campaign contracts remain experiment-specific scientific records, not competing agent instruction files.

## Project naming and GitHub migration

**Canonical project:** GREENS. **Primary researcher:** Abhinav Choudhary. **ORCID:** [0009-0001-4892-5438](https://orcid.org/0009-0001-4892-5438). Research context: IIIT-Delhi, VICAS Lab, under Dr. Anuj Grover's guidance. Existing MIT licensing is preserved; no institutional endorsement or publication metadata is invented.

Updated public locations include the README, documentation index/project/method/results/reviewer pages, artifact navigation, contribution/agent guidance, citation metadata, workflow display names, issue template, maintained analysis help, CMake project display name, and Makefile help. Stable software APIs and `GREEN` / `GREEN-ECC-PHY` scientific/source identifiers remain unchanged.

The GitHub repository itself is **not renamed**. Existing artifact URLs and frozen source/reference identities use the historical repository URL; review-policy-safe migration of external manuscript links is unresolved. The separate technical study is presented without manuscript title or venue association pending review-status confirmation. Changing the public repository URL is deferred until external artifact references and review policy can be checked. Do not rely solely on redirect behavior.

[File-level naming audit](naming-audit.csv) lists retained historical-name classes and reasons. Historical/frozen occurrences retain provenance; the active clone URL targets the existing repository while the destination directory is named GREENS. A schema URI remains a source-contract identifier.

## Public provenance cleanup

Public prose uses named scientific populations and stages, not developer commits, branches, worktrees, machine names, or private filesystem locations. The public layer retains raw tool/container identifiers only in required machine-readable integrity metadata. Original immutable execution records preserve their original representations, including the earlier simulation-capability gate audit, which is classified as historical provenance. Public result tables carry architecture, seed, timing, operation energy, and qualification information; checksums are not presented as scientific findings.

The public evidence index projects scientific quantities from frozen records. Existing immutable execution records retain locations/identifiers where their removal would break submitted evidence or integrity. They are optional low-level records and are not required to understand or execute the reviewer workflow. External repository/ORCID/DOI links and meaningful numerical constants remain. Optional tool discovery now uses PATH or `GREENS_TOOL_BIN`, replacing two developer-specific compiler-directory defaults.

## Reviewer outcome

**Yes:** an ISCAS reviewer can reproduce the supplied headline claim set without reverse-engineering the repository or knowing the author's filesystem, development branches, or internal bookkeeping. The path is root README → ISCAS artifact → reproduction / claim map / public scientific evidence.

```bash
python scripts/reproduce_iscas.py
python scripts/reproduce_iscas.py --check
```

The workflow emits admission, paired energies, operation summaries, BCH feasibility, a workload slice, conditions, automatic integrity metadata and a figure. It reproduces four primary pairs, 20 cells, 40 records, Hsiao lower in four cells, and BCH setup-feasible in zero of five seeds. Exact manuscript layout/table numbering cannot be verified because manuscript sources are outside the repository.

Full physical regeneration is separately documented and was not run for presentation validation. Current review/acceptance status is unverified. No submission PDF, release tag, DOI, or new license is created.

## Validation record

The completed CI-foundation, dependency, and reviewer-artifact subsets passed all relevant hosted checks before merging. The final public layer adds a non-mutating documentation check to fast CI; the linked workflows report its current status.

| Validation | Executed result |
|---|---|
| `make`, `make test`, `python -m pytest -q` | Native build and 502-test contract passed in the updated environment; full suite passed 741 tests before the artifact addition |
| Hosted complete Linux/Windows suite | Passed on Python 3.10/3.11/3.12 Linux and Python 3.11 UCRT64 Windows; the artifact addition brings the suite to 754 tests |
| Current and legacy CMake / CTest | Both native executables pass; CMake 3.14 compatibility is exercised explicitly |
| `python scripts/reproduce_iscas.py --check` | PASS; all 1,697 original seal entries verified; exact tracked numerical derivations reproduced |
| Admission/integrity regressions | 13 pass, including hold failure, missing/non-numeric measurements, unmatched workload, invalid denominator, changed bytes and attempted resealing |
| `python scripts/check_documentation.py` | PASS; generated sections current; 24 scientific figure-data files unchanged; original 17 rendered figures retain their declared integrity |
| Public artifact and quality checks | Local links/images, fences, YAML/JSON, Python syntax, official CFF schema and public provenance checks pass |
| Diagrams and graphics | Mermaid syntax checked; quantitative SVG and the compact vector flow visually inspected; new SVG structure validated |
| Frozen scientific paths | No changed campaign, RTL, or retained gate-record files in the cumulative diff |
| Full physical regeneration | Not executed; optional procedure and conditions are documented separately |

The maintained installation has 34 exact package definitions, including Python 3.10-only dependencies. [Dependency audit](dependencies.md) explains compatible-version choices and retained EDA environments. The seven prior maintained-lock alerts were cleared by the merged updates; remaining alerts are confined to historical environment records.

Main requires pull requests, up-to-date checks, resolved review threads, and the three named fast checks, including for administrators. The policy has zero mandatory human approvals. Merges still wait for every relevant extended/artifact check to pass.

The README uses six useful badges tied to real workflows or metadata, a compact hardware/evidence flow, and the reproduced operation/workload figure. Its organization was informed by the current [OpenROAD README](https://github.com/The-OpenROAD-Project/OpenROAD): project purpose, research flow, setup, regression, contribution and licensing. Text and graphics are original.

No scientific directories were moved and no tracked evidence was deleted. Existing MIT licensing is retained; the vendored CFF schema and physical collateral retain their upstream license terms. The established software APIs, JSON/CSV fields and source identities remain compatible.
