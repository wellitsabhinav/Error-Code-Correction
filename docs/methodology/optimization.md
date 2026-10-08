# Optimization and deterministic selection

`ecc_selector.py` evaluates candidates and performs NSGA-II nondominated sorting/crowding on normalized axes, checking its first front against independent Pareto enumeration. This is retained selector behavior, not a newly rerun evolutionary campaign.

Without constraints/policy it uses its normalized-front knee and NESII comparison. FIT/latency constraints select the epsilon-constraint path; explicit carbon policies select dynamic/static/total/balanced rules. Read returned decision metadata. The registry study separately uses lexicographic model energy, structural complexity, encoded bits, and identifier.

Feasibility, direction, normalization cohort, epsilon, ties, and evidence threshold are reproducibility inputs. Sparse campaign matrices preserve missing objectives and distinguish qualified, conditional, and diagnostic fronts. A partial front is not a global winner. See [matrix framework](../matrix-optimization.md), [registry selection](../PARETO_AND_SELECTION.md), and [ML scope](ml_advisory.md).
