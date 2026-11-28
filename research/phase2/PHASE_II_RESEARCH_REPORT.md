# Phase II research report — 2026-11-28

We investigated whether the historical ECC energy differences can be explained using internal switching and physical delay, while preserving the validated baseline and limiting storage. The historical energy arithmetic reproduces, and a small standard-cell XOR test produces observable hazards when IOPATH delays are applied correctly. The installed simulation flow also fails important interconnect, timing-check and annotation controls. The original DATE physical archives are missing locally. These findings matter because a simulation can parse SDF and exit successfully while providing unusable or incorrectly annotated activity. The physical cause of the ECC energy difference remains uncertain.

**Overall status: P2-G00 BLOCKED.** P2-G01, P2-G02 and P2-G03 production experiments were not launched past that failed prerequisite. Independent historical analysis, functional preparation, simulator qualification, storage infrastructure and reviewer traceability were completed. No physical measurements, estimator errors, ECC glitch counts or new energy rankings were fabricated.

## Completed work and preserved identities

The missing configured checkout was reconstructed with one partial/sparse clone of the verified repository. Checkout commit is `f193b9902792c798dde57534137e0075dab0aff4`; the retained scientific-input commit is `8cf245ac6ac8cb9b010c073d439f04eb204d48a1`. New files are under `research/phase2`, on branch `research/phase2-delay-characterization`. No frozen campaign was rerun or modified. A baseline manifest hashes 189 selected existing files; the package validator checks that all remain unchanged.

Two unique Hsiao files have exact-byte representation conflicts with historical contracts: current Git/checkout LF bytes differ from recorded CRLF hashes. The CRLF transformation reproduces the old expected hashes, but no byte rewrite or resealing was performed. Source identity remains explicit rather than silently normalized.

The architecture audit establishes the actual Hamming parity/syndrome construction, correction behavior, valid/reset semantics and register positions. Conventional and pipelined physical shells have one- and three-cycle latency, respectively, with II=1. The pipeline core has two registered phases and no reset; shell reset is synchronous active-low. Flat Hsiao uses 72 syndrome equalities, while hierarchical Hsiao shares high/low nibble one-hot decoders. The shell's decoder echo is raw input and is not a pipeline-aligned corrected codeword.

One operation in the historical energy denominator is a simultaneous independent encoder request and decoder request at the combined codec boundary. It is not a serial encode/decode chain or a memory-array access. Encoder/decoder energy cannot be separately extracted from the retained top-level tables.

## Gate results

| Gate | Status | Actual outcome |
|---|---|---|
| P2-G00 | BLOCKED | Baseline preservation, inventory, synthetic hazard and parser/RTL smoke work completed; full physical/model/annotation readiness fails |
| P2-G01 | BLOCKED | No matched A/B/C production energy; historical A references kept separate |
| P2-G02 | BLOCKED for new physical mechanisms | Independent historical power decomposition and mapped-structure inspection completed |
| P2-G03 | BLOCKED for energy sensitivity | Eight generated activity regimes, 96 software error-condition cases and bounded actual RTL checks completed |
| Research decision | DEFERRED | No branch A/B/C/D selected from unavailable primary measurements |

## Actual new simulation and functional results

The two-cell model assembly uses pinned public SKY130 buffer/XOR source and the corresponding specify fragments. Artificial path delays create a controlled unequal-path reconvergence test. At 1 ps resolution over [5,49) ns:

| Synthetic condition | Output binary transitions | Each high hazard pulse |
|---|---:|---:|
| Zero delay | 0 | none |
| Minimum annotated delay | 4 | 900 ps |
| Typical annotated delay | 4 | 1,800 ps |
| Maximum annotated delay | 4 | 2,700 ps |

Each annotated run has two high hazards and zero X/Z time in this window. The typical run's high occupancy is 3,600 ps. A complete-event oracle agrees with the streaming parser; aliases are counted once and zero-duration scheduler events are distinguished from observable pulses. The generic parser records three inter-edge segments in the typical output, one of which is the legitimate low interval between hazards; it is not a third glitch.

Negative controls are retained. Unassembled upstream wrappers produce four unmatched ModPath warnings. Wrong hierarchy can still produce four transitions and a zero process exit, but changes the expected pulse width. INTERCONNECT does not create the expected wire-delay hazard, and the installed compiler rejects `-ginterconnect`. Deliberate setup/hold/width violations leave the notifier unchanged. The ps-SDF/ns-model experiment does not settle in the intended window; consistent-unit synthetic success does not establish general unit handling. A 50 ps path skew is filtered by the tested 100 ps XOR path. These observations qualify only the small experiment, not routed ECC glitch behavior or silicon.

Actual current-checkout RTL passed 100 completed requests for each of the four architectures, checking encoder output, decoded payload, status flags, ordering, valid and completion count against an independent software model. Measured architectural latency is 1/3/1/1 cycles at II=1. The test holds reset four clocks before traffic; arbitrary mid-transaction reset is not newly qualified. Existing formal proofs remain historical evidence; no new universal proof is claimed.

## Historical estimates reconstructed

The following are existing post-route OpenSTA estimates, newly recalculated from frozen component tables, not new physical runs. Conditions are SKY130HD TT, 1.8 V, 25 °C, common 100 MHz and five matched seeds 11/13/17/19/23.

| Metric | Combinational mean | Pipeline mean | Mean paired pipeline change |
|---|---:|---:|---:|
| Cell area | 18,649.64 µm² | 25,587.54 µm² | +37.201864% |
| Signed-slack frequency estimate | 238.887 MHz | 349.978 MHz | +46.629355% |
| Internal power | 6.753318 mW | 7.210384 mW | +6.772352% |
| Switching power | 7.822105 mW | 3.951410 mW | −49.481332% |
| Leakage | 7.300257 nW | 9.813436 nW | +34.426794% |
| Total power | 14.575431 mW | 11.161803 mW | −23.419005% |
| Combined operation energy | 145.768881 pJ/op | 111.629196 pJ/op | −23.419005% |

Percentages are means of matched per-seed ratios, not ratios of displayed rounded means. The frequency column is not measured Fmax. Historical trace time is 1,000,100,000 ps for 100,000 useful requests. `E = P × interval / completed` therefore uses 10,001 ps/op. The `P × II / f` steady-state cross-check uses 10,000 ps/op: a common 0.01% finite-window difference. Historical reset/fill/drain time was not retroactively relabelled as trimmed steady state.

All ten historical energies reproduce within 1e-8 pJ/op. The paired energy effect has mean −23.419005%, median −23.525971%, sample standard deviation 0.582203 percentage points, and range −24.016027% to −22.518943%. Individual results are in `processed/historical_power_reanalysis.csv` and `historical_statistics.json`.

The separate flat/hierarchical Hsiao campaign reports a +1.328395% mean paired energy displacement and timing-metric effects −5.886884% to +13.105803%. The 5 ns fresh-implementation SECDED campaign reports −19.336606% mean paired energy change; those different physical identities are not mixed with the 10 ns designs. The evaluated BCH realization meets the selected 10 ns target in 0/5 attempts and remains ineligible for a valid-operation energy ranking.

## Estimators, rankings and mechanisms

No C energy reference exists, so A/C and B/C deviation, absolute deviation, mean/median/worst deviation, ranking agreement and ranking reversal are unavailable. The 60-row `power_method_comparison.csv` is an explicit status matrix; primary comparison fields are empty. Historical A energy references have separate field names. Within historical matched pairs, pipelined SECDED and flat Hsiao have the lower reported energy in 5/5 seeds each. This is not a global architecture ranking or a verified delay-aware preference.

| Mechanism | Classification | Limit |
|---|---|---|
| H1 delay-induced glitches | INCONCLUSIVE | No routed ECC internal-event measurement |
| H2 effective switched capacitance | INCONCLUSIVE | Matching DATE SPEF unavailable |
| H3 mapping/topology differences | PARTIALLY SUPPORTED | Historical mapped counts differ; causal energy contribution unresolved |
| H4 clock/sequential overhead | SUPPORTED within historical Method A | Sequential-group +70.861003%, clock-group +74.337936%; no delayed magnitude |
| H5 propagation bias | INCONCLUSIVE | A/B/C comparison unavailable |
| H6 frequency normalization explains the old paired reduction | NOT SUPPORTED within that pair | Same frequency, II and finite-window denominator; wider operating-point study open |

Switching decreases by 3.870695 mW while internal power rises by 0.457066 mW in the old accounting. This explains the numerical sum, not the physical cause. Component categories and cell-group categories are separate partitions; clock power is not added again to Total. No causal decomposition is claimed from correlated cell counts or report groups. Net-capacitance and capacitance-weighted energy results remain unavailable, and no pin/parasitic double-counting assumptions were inserted.

## Workloads, errors and statistics

Eight 1,000-payload deterministic traces cover random, alternating, low/medium/high Hamming-distance, repeated, counter and spatial regimes. Actual Hamming-distance histograms and trace hashes are retained. Ninety-six software cases cover both SECDED matrices, eight error regimes and six injection fractions. Errors are applied to valid codewords. Weight-three cases are outside SECDED guarantees; their failures/miscorrections are observations, not decoder violations of a guarantee.

At 1,000 operations, fractions 0.0001, 0.001 and 0.01 yield 0, 1 and 10 actual injected events, respectively. They cannot support a precise rare-error energy estimate. Conditional energy, workload-weighted energy validation and trace-length convergence remain unmeasured. Software-reference cases and zero-delay RTL correctness do not bypass the failed physical-energy gate.

The statistical unit is a physical placement seed, not an operation. Five deterministic matched seeds support descriptive summaries but no broad population-confidence claim. Confidence intervals are left null with an explicit reason. Exploratory 5% estimator/materiality and 1–2% convergence criteria, with 1/2/5/10% sensitivity thresholds, were recorded before any new primary energy experiment. No new primary energy dataset exists on which to apply them; historical reanalysis remains descriptive. Simulator model error is not quantified by seed spread.

## Storage and reproducibility

Initial free capacity was 26.05 GiB on C: and 77.58 GiB on G:. Existing public tools and the cached simulator were reused, with no new installed dependency or PDK. Only 22,492 bytes of public two-cell model/license source were acquired. No VM, distribution, container image or full technology ecosystem was downloaded.

All small qualification waveforms, including negative controls, are retained. Twenty-four generated activity JSON files compressed from 24,348,899 to 222,822 bytes with verified lossless round trips, saving 24,126,077 bytes. Streaming savings on production waveforms are not measured. At the recorded pre-final-report sample, retained Phase II files occupied about 4.02 MiB; final sampled file totals and host capacity are in `processed/storage_summary.json`. Git materialization had separate temporary-pack overhead with a sampled maximum of 1.92 GiB. Continuous instantaneous peak monitoring was not available. Host free-space increases are not credited as project savings.

The package includes deterministic generators, machine-readable contracts/status, SHA-256 references, command/exit/runtime logs, fixed-deadline checkpoints, bounded streaming activity, storage guards, safe scratch cleanup, compressed evidence and figure-generation scripts. Full power-compatible VCD import and coverage remain blocked. Nine PDF/SVG/PNG figure sets are produced, with unsupported requested plots explicitly identified in `reports/FIGURE_COVERAGE.md`.

## Tests, reviewer issues and decision

Phase II unit tests cover activity/window/alias/X/Z handling, independent complete-event agreement, ECC correction/detection references, exact Hamming-distance controls, energy units, storage reserves, cleanup boundaries and checkpoint identity/deadline behavior. The latest test log supplies the final pass/skip count. Native `make` and the actual RTL smoke pass. Broader `make test`, root pytest, artifact, ISCAS reproduction and documentation checks were executed but fail because the sparse checkout omits their unrelated data/modules; raw logs identify the missing inputs. This does not constitute a full repository regression pass.

The detailed reviewer matrix is in `reports/DATE_REVIEW_TRACEABILITY.md`. Pipeline placement, Hsiao structures, the operation definition, historical numerical accounting and claim boundaries are addressed. Estimator comparison, physical energy origin, workload-conditioned energy and full replay remain open. Reference [2] was recovered from the historical bibliography and its author-hosted methodology inspected; exact submitted-copy correspondence and baseline reproduction remain open.

The research decision is **deferred due to prerequisite failure**, not a measured negative physical result. Branches A/B/C lack the needed new evidence; Branch D would overstate what a blocked experiment establishes. No prediction model, architecture search, Phase III or memory-subsystem integration was started.

## Reproduction and remaining questions

From the repository root, the concise read-only checks are:

```powershell
python research/phase2/scripts/validate_phase2.py
python -m pytest -q research/phase2/tests
```

Recalculate independent results with:

```powershell
python research/phase2/scripts/audit_repository.py
python research/phase2/scripts/analyze_baseline.py
python research/phase2/scripts/workloads.py --count 1000 --seed 17 --vectors
python research/phase2/scripts/make_figures.py
python research/phase2/scripts/storage_manager.py audit --label reproduced
```

Exact executed WSL simulator commands, fresh-run-ID guidance, streaming and safe-cleanup commands are in `README.md`. Per-run command arrays, source/tool hashes, timestamps, runtime and exits are retained under `experiments/` and `raw/`. `manifests/package_sha256.json` seals only this new package; it does not reseal frozen campaigns.

To unblock the primary science, recover the exact archived DATE routed V/SPEF/SDC/DEF/ODB objects by existing hashes; provide or qualify full standard-cell timing models and interconnect/timing-check support; resolve raw source representations explicitly; and verify activity import/coverage. Then execute the single-seed matched A/B/C smoke before any five-seed or long-trace expansion. The remaining questions are whether propagated activity materially misestimates energy, whether the architectural advantage survives a qualified delayed reference, which physical mechanism dominates, and whether workload/error regimes change the preferred architecture. This execution does not answer those questions yet.

Detailed paths: `repository_audit.md`, `baseline_manifest.json`, `configs/`, `manifests/`, `experiments/`, `raw/qualification_final/`, `raw/rtl_smoke/`, `raw/validation/`, `processed/`, `figures/`, `reports/` and `tests/` within this Phase II directory.
