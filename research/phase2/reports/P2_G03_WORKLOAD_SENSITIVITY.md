# P2-G03 energy sensitivity: BLOCKED; functional preparation completed

P2-G00 has not qualified the physical activity flow. No workload-conditioned, error-conditioned, mixed-workload, convergence, or average-energy model was evaluated. Empty `conditional_energy_pj` fields are intentional. No empirical workload-dependent preferred architecture is known.

Independent preparation generated eight deterministic 1,000-payload regimes with seed 17: uniform, all-zero/all-one alternating, 4-bit, 32-bit and 60-bit Hamming-distance steps, repeated identical values, counters and rotating spatial patterns. Actual 999 adjacent-payload Hamming distances per trace, histograms and trace hashes are in `workload_characteristics.csv`. Labels are not substituted for measured input characteristics. These new traces use Python's seeded PRNG and are not falsely identified as the old SplitMix64 100,000-operation trace.

The independent software model constructs Hamming position/parity equations and Hsiao odd columns directly. Its Hsiao columns are checked against the actual v2 decoder constants. Tests exercise all 72 single-bit locations and all 2,556 double-bit pairs for one nontrivial payload in each model. This is a bounded software check, not a universal RTL proof.

Ninety-six software reference cases cover two code families, eight error regimes and fractions 0/0.0001/0.001/0.01/0.1/1. Errors are injected into valid encoded words. Data single, check single, double, adjacent weight-three, nonadjacent weight-three, correctable burst and double-error burst are separate. Weight-three outcomes remain unsupported observations and may miscorrect. Bursts are contiguous prefixes in this first controlled generator; no field rate is implied.

The generator uses exact rounded injection counts. At N=1,000, fraction 0.0001 produces zero errors, 0.001 one error, 0.01 ten errors and 0.1 one hundred errors. Low-count conditions are flagged underpowered. Overall convergence cannot justify a rare-error claim with too few injected cases.

A 100-request actual RTL smoke run verifies encoder codewords, decoded data, error flags, valid ordering, and completion count for all four current-checkout boundaries. All pass at latencies 1/3/1/1 cycles, II=1. It covers clean, single and double cases using paired payloads and code-appropriate valid codewords. No power is inferred from this zero-delay RTL check, and the Hsiao source-byte representation differences remain disclosed.

The next admitted energy study should stage representative input/error cases on one recovered placement, then length convergence at 1,000/5,000/10,000 operations, before any five-seed expansion. Validate conditional-energy mixtures against explicit mixed traces before using `Σ p_k E_k`, including pipeline overlap and burst correlation. Those validations are not yet available.
