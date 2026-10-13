# GREENS multi-ECC framework

GREEN-ECC-PHY separates mathematical code identity, systematic encoder identity, deployed decoder policy, verified capability, deployment architecture, and evidence backend. A family string is descriptive only.

## Extension contract

A candidate supplies schema-valid code and implementation manifests, exact G/H or a deterministic generator, an adapter with `encode` and `decode`, a declared error universe, and hash-bound sources/evidence. The normalized decoder contract returns `NO_ERROR`, `CORRECTED`, `DETECTED_UNCORRECTABLE`, `ABSTAINED`, `UNSUPPORTED`, or `INVALID_CONFIGURATION`. The verification harness derives `MISCORRECTED` by comparing against golden data.

Factories are loaded from manifests. The external repetition fixture demonstrates that a new code, decoder, and architecture can pass exhaustive verification without core family branching. It is a framework acceptance fixture, not a scientific candidate.

## Identity fields

Code and implementation manifests expose:

- `code_spec_id` and backward-compatible `code_id`;
- `encoder_id`;
- `implementation_id`;
- `decoder_policy_id`;
- verified, failed, and unsupported capabilities;
- compatible `architecture_id` values;
- `backend_id` and `evidence_level` in results.

Multiple decoder policies may attach to one code specification. A different G/H matrix or encoder/codeword set receives a new `code_spec_id`. Registry loading checks dimensions, rank, `G H^T=0`, source hashes, matrix hashes, manifest hashes, and all cross-references.

## Verification semantics

The verifier checks deterministic encoding, no-error identity, malformed and wrong-length inputs, latency contract, every preregistered correction/detection mask, implementation-specific claims, and hash-bound evidence. Reports include exact fractions and outcome counts for corrected data, detected/abstained outcomes, and silent miscorrections. Linear translation invariance justifies canonical-codeword mask enumeration; where not established, multiple deterministic payloads are used.

The built-in results include:

- full SECDED guarantees for Hsiao and conventional extended-Hamming;
- partial TAEC status because all 62 adjacent triples silently miscorrect;
- rejected SEC-DAEC status because 302/2,556 doubles silently miscorrect;
- rejected historical cyclic status because 33/63 singles silently miscorrect;
- a separate valid primitive BCH (63,51,t=2), plus valid shortened (71,64,t=1), (78,64,t=2), and (85,64,t=3) references;
- eight distinct archived SafeForge/CodeForge matrix/table policies.

## Valid primitive BCH plugin

`green_ecc_phy/bch.py` verifies primitive polynomials, builds binary cyclotomic cosets and the conjugate-root generator, emits systematic G/H matrices, computes GF syndromes, and creates a deterministic bounded syndrome locator. Shortening fixes and removes parent information coordinates while preserving their parent polynomial exponents. The historical invalid RTL polynomial is never modified or reused.

## Exact versus analytical versus physical

Exact metrics are matrix dimensions, rate, distances when proved, exhaustive functional fractions, normalized encoded bits, padding/fragmentation, and structural operation counts. Analytical metrics carry `{value, unit, model_id, parameter_provenance, evidence_level, sensitivity_interval}`. Physical fields use the existing physical schema and remain null unless a genuine backend, PDK/library/corner, timing/activity setup, and evidence record exist.

The scenario model is preregistered in `green_ecc_physical_simulation/registry/scenarios/software-simulation-study-v1.json`. Its fault probabilities and energy coefficients are explicitly labelled uncalibrated sensitivity parameters—not measurements.

## Fair payload comparison

Normalization covers one information bit, a protected 64-bit word, a 512-bit cache line, equal workload, equal reliability requirement, and equal information capacity. `ceil(payload/k)` codewords are charged. Padding and fragmentation are explicit. A (63,51) candidate therefore uses 126 encoded bits for a 64-bit payload rather than being compared directly with one 72-bit SECDED codeword.

## Architecture compatibility and null physical policy

The full implementation x architecture matrix classifies combinations as compatible/evaluated, compatible/not evaluated, or incompatible, with a separate physical status of `blocked_by_missing_physical_evidence`. Fixed, configurable, and adaptive identities do not transfer MUX/controller/metadata/transition costs into code metrics.

Structural Yosys evidence stays in `structural_metrics`. Physical cell/routed area, delay, power, energy, routing, MUX/controller cost, transition/re-encoding cost, and physical uncertainty stay null. The physical selector continues to return no winner.

## Commands

```text
python scripts/build_multi_ecc_catalogue.py
python scripts/run_multi_ecc_framework_evaluation.py
python eccsim.py ecc list
python eccsim.py ecc inspect --code primitive-bch-63-51-t2-v1
python eccsim.py ecc verify --implementation primitive-bch-63-51-t2-v1-reference-decoder
```

Use `--registry` with the ECC CLI for an external catalogue. The complete software-study artifacts and traceable plots are under `green_ecc_physical_simulation/multi_ecc_evaluation`.
