# GREENS methodology

## Evidence-qualified decision chain

GREENS applies **Service → Identity → Feasibility → Operation → Lifecycle**. Declare the W1/W2 protection contract, bind the exact RTL and macro organization, check route/setup/hold, qualify matched operation activity/parasitics and energy, then compare lifecycle expressions only across matched boundaries. Missing operands remain unavailable or symbolic.

The [ISCAS primary cohort](../experiments/iscas/README.md) requires both members of each seed pair to pass setup and hold and provide all five operation classes. Historical setup-only flags do not override hold failures. The [claim index](../experiments/iscas/claims.md) connects each result to its calculation and evidence.

## Research question

How should SRAM ECC architectures be evaluated and selected when reliability, physical implementation cost, operational energy, latency, and lifecycle/sustainability considerations must be considered jointly rather than independently?

GREENS operationalizes only the portions for which evidence is present. A blocked absolute conclusion is a valid methodological result.

## Hypotheses

The repository contains several studies with their own frozen hypotheses. At framework level, the working propositions are:

1. a family name is insufficient to establish decoder behavior;
2. logical fault response and physical fault occurrence must be separated;
3. structural or vectorless estimates may not preserve activity-aware ordering;
4. multi-objective selection must apply evidence and feasibility gates before ranking;
5. lifecycle conclusions depend on explicit energy, grid, manufacturing, yield, lifetime, and boundary assumptions.

Campaign-specific hypotheses and materiality thresholds are authoritative in their contracts and reports; this page does not replace them.

## Independent variables

- ECC mathematical code and concrete implementation/policy;
- deployment architecture and interleaving proposal;
- payload/codeword width;
- SRAM/macro configuration;
- clock target and physical seed;
- logical fault class or declared physical fault scenario;
- voltage, temperature, technology/PVT, workload, scrub and service policy;
- use-grid, manufacturing-grid, lifetime, yield, allocation, and boundary scenarios.

## Dependent variables

Depending on evidence availability: correction/detection/SDC/DUE outcome fractions, FIT, area, wirelength, via count, setup/hold timing, power components, operation energy, service energy, operational carbon, lifecycle carbon, Pareto membership, and decision status.

## Controlled variables

Matched comparisons hold constant useful payload, capacity or functional unit, wrapper policy, tool image and commit, PDK/library/corner, clock constraint, workload, activity window, seed set, and extraction boundary. Each campaign records the subset actually controlled. Missing controls reduce qualification rather than being assumed equal.

## ECC population

The general registry currently contains 15 code specifications and 17 implementations. The matched physical population is narrower: U0, conventional SECDED, Hsiao SECDED, and BCH(78,64,t=2). SEC-DAEC is retained as a failed functional candidate and excluded from that physical population. See [ECC architectures](ecc-architectures.md).

## SRAM population

The current matched SKY130 study uses inherited SRAM22 256×64 and 256×8 views to construct the required interfaces. Those are not fresh OpenRAM outputs. A fresh 256×72, 1RW, one-bank OpenRAM attempt at TT/1.8 V/25 °C timed out before DRC, LVS, or characterization completed.

## Fault population

Exact logical verification enumerates only declared error universes. Campaign controls include SBU, arbitrary two-bit errors, and consecutive logical MBU classes. Analytical PMFs are assumptions. No qualified physical event distribution or complete bitcell/logical mapping currently converts those logical responses into absolute physical SDC/DUE/FIT.

## Physical-design population

The frozen matched population spans four architectures, 10 ns and 5 ns, and seeds 11, 13, 17, 19, and 23: 40 inherited runs. The additive v3.3 campaign contains ten fresh 10 ns SECDED/Hsiao runs. U0, SECDED, and Hsiao were timing-feasible at 10 ns in the inherited population; only U0 was feasible at 5 ns. Failed timing points remain evidence.

## Sustainability parameters

Operational energy is partitioned by operation when evidence permits. Use-grid intensity translates joules to operational carbon. Manufacturing/lifecycle calculations require route, process-gas, electricity, upstream, wafer, yield, die allocation, packaging, lifetime, workload, and replacement assumptions. Current SKY130-native manufacturing/lifecycle evidence is insufficient for an absolute result.

## Experimental procedure

1. Freeze code, configuration, tool, environment, workload, seed, and claim boundary.
2. Validate mathematical/decoder identity and functional behavior.
3. Execute logical, structural, or physical flow as authorized.
4. Preserve raw logs, failures, reports, timestamps, commands, and hashes.
5. Normalize quantities into evidence records with units and boundaries.
6. Apply evidence compatibility, fairness, and feasibility gates.
7. Compute conditional metrics and non-dominance only from eligible records.
8. Report qualified conclusions and unresolved operands separately.

## Evidence qualification

Qualification is quantity- and use-specific. E5 activity-qualified logic power is valid for the bound ECC-logic operation window; it does not qualify macro-internal energy. See [Evidence model](evidence-model.md).

## Statistical analysis

Exact enumeration is reported as exact within its declared universe. Physical seed populations are descriptive samples with matched-pair summaries; a five-seed sample is not a silicon population. Deterministic sensitivity tuples and Latin-hypercube scenarios are model exploration unless a statistical sampling design says otherwise. Monte Carlo runs must record the PRNG, seed, number of trials, outcome definition, and uncertainty interpretation.

## Multi-objective analysis

Eligibility precedes dominance. Objectives retain units and directions. The repository includes exact Pareto enumeration, geometric knee and 2D hypervolume audit utilities, and deterministic policies. Scalar ESII/GS/GSE/GCI-style metrics remain optional policy/model constructs, not universal scientific orderings. See [Matrix and optimization](matrix-optimization.md).

## Threats to validity

Internal validity is limited by model correctness, incomplete macro activity, small seed populations, and historical tool-flow exceptions. Construct validity is limited when structural proxies stand in for unmeasured physical quantities. External validity is limited by SKY130/SRAM22 context, absence of silicon/radiation measurement, chosen workloads, and logical fault abstractions. Conclusion validity is limited wherever populations are descriptive or scenario weights are policy choices. These limitations are not repaired by adding more decimal precision.
