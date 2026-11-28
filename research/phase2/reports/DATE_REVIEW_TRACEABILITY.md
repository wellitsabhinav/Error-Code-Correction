# DATE reviewer traceability

This matrix addresses the concerns supplied in the request. Original reviewer letters and the exact submitted PDF were not available; no acceptance, venue outcome or submitted-copy identity is asserted.

| Reviewer | Concern | Status | Evidence / remaining work |
|---|---|---|---|
| 1 | Clarify methodological contribution | PARTIALLY RESOLVED | Explicit A/B/C contract and qualified versus blocked evidence; new estimator findings remain open |
| 1 | Separate scientific methodology from implementation | RESOLVED | Readiness distinguishes model assembly and simulator observations from physical conclusions |
| 1 | Findings beyond established PPA tradeoffs | OPEN | No primary delay-aware comparison; novelty decision deferred |
| 2 | Compare evaluation methods | OPEN | P2-G01 blocked; 60 explicit status records retain unavailable results |
| 2 | Quantify estimator deviation | OPEN | No valid C reference; all deviation fields null |
| 2 | Internal switching and delay effects | PARTIALLY RESOLVED | Two-cell synthetic hazards measured; routed ECC events absent |
| 2 | Exercise correction paths | PARTIALLY RESOLVED | Software all-single/all-double masks and four RTL boundary smoke tests; error-conditioned physical energy open |
| 2 | SKY130HD limitations | RESOLVED as claim boundary | One TT corner, 1.8 V/25 °C, standard-cell/Liberty simulation; no modern-node or silicon extrapolation |
| 2 | Standalone codec versus memory subsystem | RESOLVED | Functional unit is two independent codec channels; SRAM internal energy/controller/interconnect outside boundary |
| 2 | BCH timing failure | RESOLVED | Historical implementation meets common timing target in 0/5 attempts; no valid-operation energy extrapolation |
| 2 | Reference [2] baseline | PARTIALLY RESOLVED | Recovered revision-3 BBL and author-hosted paper inspected; original benchmark traces and reproduction unavailable |
| 3 | Reconstruct transformations | PARTIALLY RESOLVED | Actual RTL/register cuts, source hashes, mapped JSON; source-byte representation conflicts disclosed |
| 3 | Actual circuit examples | RESOLVED | Pipeline cut diagram, syndrome 0x07 correction example and extracted mapped XOR connectivity |
| 3 | Explain numerical results | RESOLVED for historical accounting | Ten energy reconstructions and component/group partitions; causal explanation remains open |
| 3 | Reproducibility | PARTIALLY RESOLVED | Commands, package hashes, retained failures, streaming tests and small VCDs; missing physical archives prevent full replay |
| 4 | Pipeline register placement | RESOLVED | Actual source audit and functional latencies 1/3 cycles, II=1 |
| 4 | Flat versus hierarchical Hsiao | RESOLVED | Shared syndrome/encoder; 72 equalities versus high/low nibble decoding; mapped counts retained |
| 4 | Define an ECC operation | RESOLVED | One simultaneous independent encode/decode request; counts and finite-window overhead explicit |
| 4 | Physical origin of energy differences | OPEN | H1/H2/H5 remain inconclusive; Method A overhead accounting is not causal evidence |
| 4 | Actionable design tradeoffs | PARTIALLY RESOLVED | Historical energy/area/latency/estimated-frequency tradeoff; no universal winner or adaptation algorithm |

## Recovered reference [2]

The second `bibitem` in the recovered revision-3 BBL is Ghosh, Basu and Touba, *Reducing Power Consumption in Memory ECC Checkers*, ITC 2004, DOI 10.1109/TEST.2004.1387407. The BBL is tied to historical branch commit `9968f9b15f949d38faf944a3546ea736cfab63df`; correspondence to the reviewer's exact submitted copy remains unverified. [Recovered BBL](https://github.com/wellitsabhinav/Error-Code-Correction/blob/9968f9b15f949d38faf944a3546ea736cfab63df/paper/date2027_revision3/date2027_revision3.bbl).

The author-hosted paper's Sections 5–6 use SimpleScalar memory-access traces from SPEC and MediaBench, SIS synthesis with two-input XOR primitives, and XOR-output transition counts as the power surrogate. Inputs are synchronized and glitch power is excluded. It explores column/input choices with simulated annealing and genetic search against 100 random solutions. The GA settings are population 250, elites 5, mutants 50, bottom 100 filtered, and 200 generations. [Author PDF](https://users.ece.utexas.edu/~touba/research/itc04-mem.pdf).

For this project, reproduce that logical transition-count estimator as a separate parity-generator baseline once the original trace/circuit identities are available. Match the functional boundary before comparing it to B or C, then separately test routed Liberty/SPEF energy. This is a proposed compatibility-controlled reproduction, not an executed optimization or a claim that the old study included physical glitches. No licensed SPEC trace or proprietary synthesis tool was acquired.
