# GREENS SafeForge method and claim boundary

SafeForge is a finite-support, distributionally robust compiler for SRAM ECC policies. Given a systematic binary matrix, a nominal conditional fault PMF, an expanded bit-exact error support, and an explicit ambiguity set, it executes the actual decoder for every error vector and compiles each nonzero syndrome to either `correct(error_vector)` or deliberate `DUE`.

For every policy it computes separate binary loss vectors for silent corruption, deliberate failure, and correct recovery. It never folds SDC and DUE into a weighted score. The optimization hierarchy is:

1. satisfy worst-case SDC;
2. satisfy worst-case residual FIT when a raw FIT and limit are supplied;
3. minimize worst-case DUE;
4. minimize nominal DUE;
5. minimize the technology-independent hardware proxy.

## Ambiguity models

`total_variation` uses exact probability transfer and its closed-form binary-loss dual. `structured_interval` is a normalized linear program with simultaneous pattern, category, and union-of-category aggregate bounds for family, multiplicity, adjacency class, burst length, VDD, temperature, and spatial region. The aggregate form directly encodes statements such as `P(multiplicity >= 2) in [l,u]` without inventing bit-exact observations. `geometry_wasserstein` uses an exact fractional transport construction and finite dual breakpoints for binary loss. Its ground cost combines multiplicity change, error-vector Hamming distance, upset displacement, burst-span difference, adjacency-class change, and SRAM row/column centroid distance.

Each certificate contains the primal adversarial PMF, a dual bound, status, gap, patterns receiving probability, and a content hash. The independent verifier does not invoke an optimizer: it re-executes the matrix and policy, validates PMFs and loss vectors, checks TV/interval/transport feasibility, reconstructs the dual bound, and verifies tightness and hashes.

The certified safety radius `delta*` is the largest radius, to numerical tolerance, at which worst-case SDC stays below the configured limit **on the named support**. For probability `eta` outside that support, the complete risk is bounded by `(1-eta)R_SDC,S + eta B_out`, with `B_out=1` unless a tighter execution proof is available. An engineering radius is not described as a confidence bound. Statistical coverage is emitted only by the Clopper-Pearson/Bonferroni sample-calibration utilities and only under their stated independent, stationary sampling assumptions.

Every hardened metric row binds the experiment, matrix, decoder policy, nominal/adversarial PMF, ambiguity type/radius, error universe, parity budget, physical mapping, and scope. Nominal and held-out correction/DUE/SDC form probability partitions. Worst-case SDC and DUE are separately maximized bounds and are never displayed as if they formed a partition with nominal correction.

## Search scopes

For `r <= 4` and zero SDC, exact co-synthesis enumerates every ordered selection of distinct nonzero, non-basis systematic data columns. For each matrix it constructs the maximal action set that is SDC-free for every PMF on the declared support, then applies the safety-first hierarchy. The search visits all 7,920 `(8,4)` ordered candidates and proves optimality within that explicit scope.

For 64 data bits, arbitrary-matrix co-synthesis is retained as a negative scalability result. Practical evaluation fixes conventional extended-Hamming SECDED, Hsiao SECDED, or an existing generated `(72,64)` matrix and compiles decisions over its 255 nonzero syndrome classes. The frozen deterministic class rule generates certified feasible SDC-DUE operating points. It is not presented as a globally optimal constrained frontier. The physical-column mapping search remains a verified heuristic, not a global optimum.

## Deployment rule

Each deployable mode registers its fault-model family, ambiguity type, `delta*`, maximum certified SDC/DUE, out-of-support probability limit, independently verified certificate hash/version/integrity, fallback, and certificate ID. The strict scheduler may select a specialized mode only when the current confidence region is contained in that mode's envelope, tail probability is bounded, and the SDC certificate satisfies system policy. Otherwise it selects a separately certified fallback or reports that no certified mode exists. Nominal score cannot override this gate. The strict checks are additive and opt-in to preserve the existing CLI/schema behavior.

## Hardware scope

Generated SystemVerilog contains the encoder/syndrome network, correction-mask/action table, abstain/DUE signal, 128-bit safety-envelope identifier, envelope-valid input, fallback selection, and no-certified-mode signal. The validation runner archives Icarus execution, Verilator lint, and Yosys/ABC generic cell/depth reports with exact versions and commands. Structural XOR/table and generic-cell counts are not physical area, timing, power, or PPA. Physical claims require a characterized library and synthesis/place-and-route flow.
