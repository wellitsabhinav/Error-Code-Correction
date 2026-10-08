# Fault generation and reliability

SBU flips one logical bit. DBU flips two; arbitrary pairs and adjacent pairs are different universes. MBU/burst experiments record mask/PMF, codeword width, adjacency convention, capacity, seed, and duration/iteration count. `mbu.py` has intentionally simple burst presets, not measured radiation footprints.

Exact verification computes conditional decoder outcomes over a finite declared universe. Absolute rates additionally require `lambda_class` in events/hour and verified bitcell mapping: `lambda_outcome=sum(lambda_class*P(outcome|class))`; `FIT=1e9*lambda_outcome`. Current physical SDC/DUE/SER/FIT remains blocked.

Scrub calculations use a declared Poisson model: `P(K=k)=exp(-lambda*T)*(lambda*T)^k/k!`, with interval T in hours. Periodic scrub and scrub-on-correct differ; retain configuration and corrected-event accounting. State whether energy includes scrub and reliability is per device/capacity/codeword.

A tiny smoke is `python eccsim.py sram simulate --size-kb 64 --word-bits 8 --scheme sec-ded --iterations 100 --seed 17 --json`. It checks software without establishing long-term physical reliability. See [main guide](../reliability-model.md), [Qcrit](qcrit.md), and [fault evidence](../FAULT_EVIDENCE.md).
