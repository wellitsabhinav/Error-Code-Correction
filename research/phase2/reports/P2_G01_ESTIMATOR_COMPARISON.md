# P2-G01 estimator comparison: BLOCKED at P2-G00

There are no newly qualified Methods A/B/C results on the same physical ECC implementation. Relative deviation, mean absolute relative deviation, median/worst deviation, paired confidence intervals, and ranking agreement/reversal are unavailable. Missing values remain empty/null, never zero.

`processed/power_method_comparison.csv` contains 60 explicit status rows: four architectures × five seeds × three methods. The A rows carry a separately named historical energy reference; their primary comparison fields are empty because the new steady-state observation window has not been matched. B and C are blocked. This file is a status dataset, not a measured comparison table. `architecture_ranking_comparison.csv` retains the ten historical within-pair rankings and leaves B/C and agreement fields unavailable. It makes no global ranking across unrelated physical campaigns.

## What the existing evidence does establish

Recalculation from the existing full-precision component CSV reproduces all ten SECDED historical energy values to 1e-8 pJ/op. Mean energy is 145.768881 pJ/op for combinational and 111.629196 pJ/op for pipelined. Mean paired change is −23.419005%; every seed has the same direction. These remain post-route activity-propagated estimates.

The historical period is 10 ns (100 MHz), II is one, voltage 1.8 V, temperature 25 °C, and each trace contains 100,000 useful requests. Total recorded trace time is 1,000,100,000 ps = 1.0001 ms. Thus `E[pJ/op] = P[W] × interval[ps] / N` uses 10,001 ps/op, while the ideal steady-state cross-check uses 10,000 ps/op. The finite-trace overhead is 0.01% for both architectures. Historical figures include that full interval; they are not relabelled as newly trimmed steady-state estimates.

One useful request comprises one independent encoder operation and one independent decoder operation at the same characterization boundary. It is not a serial encode-then-decode transaction and not an SRAM access. Encoder/decoder power cannot be separately recovered from the retained top-level component tables.

## Required matched comparison

Use the exact same routed netlist, SDC, parasitics, corner, logical sequence, frequency and completed count for each A/B/C triplet. Capture B/C internal VCD at a qualified resolution; retain small raw windows and stream larger activity. Verify functional results, hierarchy aliases, unknown durations, start/end boundaries, clock/reset activity, internal-net coverage, and whether imported activity survives power propagation. A compact toggle summary is not assumed to be an OpenSTA-compatible power input. Effective throughput, timing slack, all power categories, completion count and runtime/storage measurements remain required before admitting energy.

Begin with the first matched seed and 100/1,000 operations. Expand sequentially through 5,000/10,000 only after convergence and annotation checks; use 25,000 or 100,000 only when justified. No such expansion was launched in this execution.
