# GREENS SafeForge hardening report

The artifact is frozen around one contribution:

> SafeForge is an SRAM-oriented certifying compiler that generates syndrome correction/abstention policies, synthesizable RTL, and independently verifiable worst-case SDC bounds under explicit fault-distribution uncertainty.

The full paper draft is `docs/SAFEFORGE_MANUSCRIPT.md`; this report records the acceptance evidence and claim boundary.

## Acceptance evidence

| Requirement | Result | Artifact |
|---|---|---|
| Full 8-bit universe | all 255 nonzero vectors, five decoders, four disjoint outcomes | `reports/safeforge_hardening/support_audit_8bit.json` |
| Support and tail risk | per-universe radii plus complete `(1-eta)R + eta B_out` bounds | `docs/SAFEFORGE_SUPPORT_AUDIT.md` |
| 72-bit bounded universe | exactly 1,091,058 vectors through weight four; weight>4 tail remains explicit and unbounded without `eta_gt4` | `reports/safeforge_hardening/weight_le4_72bit_audit.json` |
| Metric context | experiment/matrix/policy/PMF/ambiguity/universe/parity/mapping/scope on each row; mixed identities rejected | `reports/safeforge_hardening/metric_context_table.json` |
| Gain source | controlled matrix, placement, syndrome-policy, abstention, and PMF pairs | `reports/safeforge_hardening/gain_source_ablations.json` |
| Practical fixed code | conventional SECDED and Hsiao `(72,64)`, existing generated matrices, and robust mapping | `reports/safeforge_hardening/fixed_72bit_risk_frontiers.json` |
| Risk frontier | TV radii `0` through `0.1`, SDC budgets `0` through `0.2`, 324 contextualized achieved points | same artifact and `figures/sdc_due_risk_frontier.svg` |
| External evidence | three separate source-specific aggregate ambiguity sets; nine policy/certificate evaluations | same artifact plus `data/fault_evidence/sources.json` |
| Solver-independent verification | all literature structured-risk certificates independently replayed and verified | same artifact |
| RTL/synthesis | Icarus campaigns, Verilator lint, Yosys/ABC structure, full logs and versions | `reports/safeforge_hardware_validation/` |
| Scheduler | strict support/radius/tail/hash/version/verification/SDC gate and certified fallback rule | `architecture/schedule_pipeline.py`, `tests/python/test_safeforge.py` |

## Reconciled small-study metrics

All rows below belong to the SafeForge hardening experiment and the declared 28-pattern universe. Nominal rows are partitions. Worst-case SDC and DUE are separate TV-radius-0.1 maxima and do not form a partition.

| Strategy | Nominal correct | Nominal DUE | Nominal SDC | Worst SDC | Worst DUE |
|---|---:|---:|---:|---:|---:|
| Conventional single-bit decoder | 0.48 | 0.52 | 0 | 0.10 | 0.62 |
| Nominal ML, fixed Hsiao | 0.93 | 0 | 0.07 | 0.17 | 0 |
| Robust abstain, fixed Hsiao | 0.11 | 0.89 | 0 | 0 | 0.99 |
| Nominal synthesized matrix | 0.97 | 0 | 0.03 | 0.13 | 0 |
| Robust co-synthesized matrix/policy | 0.64 | 0.36 | 0 | 0 | 0.46 |

The `0.97` correction result is not a new-code gain: the matrix is extended-Hamming/Hsiao-equivalent. In controlled pairs, changing only the equivalent matrix under a single-bit decoder changes correction by `0`; the syndrome/coset-leader policy contributes `+0.45`; the tested PMF specialization contributes `0`; and robust physical placement changes zero-SDC policy correction by `+0.44`. Abstention reduces worst-case SDC by `0.17` relative to nominal ML but adds `0.89` nominal DUE.

## Support audit result

The fixed and co-synthesized robust policies have `delta*=1` only on the 28-pattern support. Their zero-SDC radius is zero on weight-at-most-two, weight-at-most-three, and complete universes. Across all 255 errors, fixed robust records 60 SDC outcomes and co-synthesized robust records 135. No universal safety claim survives the audit.

## Fixed-code frontier result

At TV radius `0.05`, fixed Hsiao moves from `(worst SDC, worst DUE) = (0,1)` at zero SDC budget to `(0.05,0.6672)` at `epsilon=0.05` and `(0.0861,0.5364)` at `epsilon=0.1`. Nominal correction rises from `0.0394` to `0.3828` and `0.4774`. This materially improves on the `0.9606` nominal DUE zero-SDC point, but no epsilon is preferred without a system reliability target. Points are certified feasible under the frozen deterministic syndrome-class rule; global frontier optimality is not claimed.

The 64-bit arbitrary-matrix search remains negative. No verified dimension-matched SEC-DAEC artifact exists. The TAEC wrapper has a triple/single collision, and the `(63,51)` BCH example has an unverified-distance triple collision; both are retained as negative tests.

## Literature and hardware evidence

Literature aggregates are represented as structured ambiguity constraints, not bit-exact PMFs. The alpha, neutron, and undervolting sets remain source-specific and synthetic performance results remain separately labeled. Under the broad alpha constraint, nonzero-risk policies can reach worst-case SDC one; the support-universal zero-SDC policy instead reaches worst-case DUE one.

Actual local logs record passing Icarus ASIC and SafeForge campaigns, passing generic Yosys/ABC synthesis, and tool versions. The same-matrix nominal/robust comparison reports 311 versus 380 generic cells and longest paths 38 versus 40 cells. These are generic structural results only. The observed Linux CI run at the pre-hardening commit failed in the generic RTL regression before SafeForge steps; the updated workflow always archives the complete runner output. A Linux pass must not be claimed until that workflow runs successfully on the changed tree.

## Frozen limitations

- no fundamentally new `(8,4)` code;
- no safety beyond the named support without an explicit tail bound;
- no practical or globally optimal 64-bit matrix co-synthesis;
- no measured SafeForge silicon behavior or bit-exact radiation PMF;
- no physical area, delay, energy, leakage, or PPA without a characterized library;
- no preferred SDC budget without a system-level reliability requirement;
- no superior shared-hardware claim.

Regenerate the scientific and hardware artifacts with:

```bash
python scripts/run_safeforge_hardening.py
python scripts/run_safeforge_hardware_validation.py
```
