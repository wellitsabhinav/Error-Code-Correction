# Architecture

GREENS has a reusable software layer and an additive campaign-evidence layer. The reusable layer registers identities, verifies behavior, normalizes results, and analyzes scenarios. Campaign directories bind that machinery to exact tools, PDKs, clocks, seeds, workloads, and immutable source hashes.

```text
Code/implementation manifests ------> schema + hash validation
          |                                      |
          v                                      v
  encoder/decoder adapter ------------> exact functional gate
          |                                      |
          |                         rejected records retained
          v
 deployment + backend compatibility
          |
          +--------------------+----------------------+
          |                    |                      |
          v                    v                      v
 analytical reliability   RTL/structural       matched PnR/activity
          |                    |                      |
          +--------------------+----------------------+
                               v
                    evidence normalization (M_E)
                               |
                    +----------+-----------+
                    |                      |
                    v                      v
             physical matrix (M_P)  scenario/lifecycle (M_S)
                    |                      |
                    +----------+-----------+
                               v
                   constraints -> Pareto -> decision
                               |
                               v
                 qualified conclusion or blocker
```

## Major modules

| Module | Responsibility |
|---|---|
| `eccsim.py`, `green_ecc_phy/cli.py` | Stable command interface and dispatch |
| `green_ecc_phy/registry.py`, `loading.py` | Schema, identity, source-hash, and factory resolution |
| `green_ecc_phy/adapters.py`, `bch.py` | Normalized encode/decode policies |
| `green_ecc_phy/verification.py` | Declared-universe enumeration, golden-data comparison, counterexamples |
| `green_ecc_phy/backends.py`, `comparison.py` | Null-safe physical records, fairness views, physical-only eligibility |
| `green_ecc_phy/study.py` | Equal-payload normalization and analytical scenario study |
| `architecture/` | Deployment topology, scheduling, transitions, and architecture-aware DSE |
| `analysis/` | Pareto, knee, hypervolume, sensitivity, workload, and plotting utilities |
| `ml/` | Optional advisory model; deterministic selector remains authoritative |
| `validation/` | Environment and output sanity checks |
| `campaigns/iscas_sustainability_extension/` | Frozen and additive physical, reliability, energy, and sustainability evidence |

## Configuration flow

The versioned registry is rooted at `green_ecc_physical_simulation/registry/registry.json`; its records refer to code, implementation, architecture, backend, workload, and scenario manifests. User-facing examples under `configs/` feed CLI workflows. JSON Schema contracts under `schemas/` validate major configuration and result types. Campaign-specific `config/` or `configs/` directories freeze the parameters used for an evidence population.

Configuration identity and implementation identity are distinct. A code such as extended Hamming SECDED can have multiple decoder policies and deployment forms. A result is meaningful only after code, implementation, architecture, backend, PDK/library/corner, workload, fault model, seed, and boundary are bound.

## Experiment orchestration

Reusable scripts under `scripts/` rebuild the registry study, documentation, code-synthesis studies, or transition studies. Physical controllers live with their campaigns because their frozen image, deadline, and external evidence roots are experiment-specific. The completed v3.3 controller loads a persisted campaign start/deadline; it does not allocate a fresh 15-hour budget on resume.

## Artifact generation

Writers use sorted JSON, stable identifiers, fixed seeds where randomness is intended, and SHA-256 references. Results normally contain a manifest that records the repository commit, dirty state, input hashes, tool identity, command, seed, and generated-file hashes. Historical paths inside executed command records are preserved as provenance; current public scripts should use repository-relative paths or explicit environment/configuration values.

## Evidence ingestion and analysis

`M_E` records what a quantity means and whether it is usable. `M_P` stores implementation observations; `M_S` translates eligible observations into declared scenarios. Selection first applies functional, fairness, evidence, and constraint gates. It then computes non-dominance or a declared deterministic policy. Null data never becomes zero, and one qualified layer never promotes another.

For the generated registry-only view, see [System architecture](SYSTEM_ARCHITECTURE.md). For the campaign workflow, see [Experiment pipeline](experiment-pipeline.md).
