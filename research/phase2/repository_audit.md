# Repository and baseline audit

Audit date: 2026-11-28. Checkout identity: `f193b9902792c798dde57534137e0075dab0aff4`. Historical scientific-input reference: `8cf245ac6ac8cb9b010c073d439f04eb204d48a1`. Work branch: `research/phase2-delay-characterization`.

The configured checkout did not exist. `G:/ECC Continued` and `D:/R&D/ECC` were empty. The connected GitHub account verified `wellitsabhinav/Error-Code-Correction`; a single partial clone with no LFS smudge and a sparse working tree was acquired at the configured path. No baseline campaign was regenerated. The tree index inventories all 11,471 tracked paths, including paths intentionally absent from the working tree. Absence in a sparse checkout is distinguished from absence in the Git tree.

The root `AGENTS.md` and `docs/adding-an-experiment.md` were inspected. The user-requested `research/phase2` root overrides the usual new-campaign-directory convention. Frozen v3.3 campaigns were not resumed. Paper/submission PDFs were not added.

| Evidence | Existing path or reference | Qualification boundary |
|---|---|---|
| Conventional core | `scripts/gate03r/rtl/secded_characterization_tops.sv` | Package-free exact conventional encoder/decoder |
| Pipeline core | `asic/rtl/secded/secded_pipelined_72_64_v1.sv` | No reset or backpressure in core; valid required |
| Evaluated physical shells | `scripts/gate04/rtl/gate04_boundaries.sv` | Independent encoder and decoder channels with shell registers |
| Flat Hsiao | `scripts/revision2/rtl/rev2_hsiao_boundary.sv` and `green_ecc_physical_simulation/rtl/hsiao_secded_72_64/` | v2 algorithmic decoder, 72 constant syndrome comparisons |
| Hierarchical Hsiao | `campaigns/date_2027_breadth_remediation/rtl/` | v3 shared high/low nibble decoders and column conjunctions |
| Formal evidence | `docs/date2027/rigour_gate_03r/`, breadth `formal/results/` | Existing proofs preserved; no new universal proof claimed |
| Common flow and PVT | `scripts/revision2/contract_v1.json`, breadth `physical/contract_v1.json` | SKY130HD TT, 1.8 V, 25 °C, 10 ns, seeds 11/13/17/19/23 |
| SDC / power commands | Revision-2 and breadth `configs/ecc.sdc`, `power.tcl` | Input-only VCD propagation; exact historical report precision |
| Primary historical tables | `docs/date2027/revision2/results/REV2_RUN_RESULTS.csv`, breadth `analysis/B_power_components_per_seed.csv` | Existing post-route power estimates, not silicon |
| Flat/hierarchical mapped netlists | breadth `synthesis/baseline_flat/` and `synthesis/new_hierarchical/` | Common synthesis outputs; not routed netlists |
| DATE routed V/SPEF/SDC/DEF/ODB | Archive member manifests in `archives/manifests/`; selected exact members in `manifests/archived_physical_references.json` | Original `D:/GREENS_ARCHIVES` and Ubuntu run roots unavailable |
| DATE SDF | No SDF member in the retained Revision-2 archive manifest | Must be generated from matching physical timing data after recovery |
| Liberty | Existing ORFS image path `/OpenROAD-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib` | SHA-256 `ec0e1067a35c8bf20b11e58d1e8ac53326067e4dac84a125cc1b917a3518d0d9` matches frozen environment |
| Full standard-cell timing models | Not available in discovered baseline environment | Two public cells acquired for a bounded synthetic probe only |
| Workload definitions | `docs/date2027/rigour_gate_03f/ACTIVITY_TRACE_MANIFEST.json`, trace-generation scripts | Historical SplitMix64 payload seed 104375203646206; 100,000 operations |
| Bibliography | Revision-3 historical branch, commit `9968f9b15f949d38faf944a3546ea736cfab63df` | Ref. [2] recovered from compiled BBL; submitted-copy identity not established |

The existing ISCAS routed files elsewhere in the Git tree are different implementations and were not substituted for the missing DATE designs.

## Actual architecture

Conventional Hamming uses positions 1–71, with parity at powers of two; native bit 71 is overall parity. The seven-bit syndrome identifies a positional error. Odd overall parity plus a nonzero valid position corrects that bit; zero syndrome plus odd parity corrects overall parity. Nonzero syndrome plus even parity reports a double error without correction. Behavior beyond the guaranteed SECDED universe remains implementation-specific.

The pipeline encoder computes all seven factored parity equations before `positional_q`; the next register stores `{^positional_q, positional_q}`. The decoder registers syndrome, overall mismatch and received word together, then classifies errors, creates a correction mask, XORs the word and extracts payload into output registers. The core contains two register phases per independent channel. Shell input/output registers produce one-cycle versus three-cycle request-to-response latency, confirmed with actual RTL simulation; II is one for both. There is one rising-edge clock and no CDC or backpressure.

Shell `rst_ni` is synchronous active-low; pipeline cores have no reset. The smoke test held reset for four clocks before traffic. Mid-transaction reset and arbitrary reset duration were not newly qualified. Invalid-cycle data may continue switching because valid is not general clock gating. The shell decoder echo is a raw received-word echo; in the pipelined shell it is registered from `dec_codeword_q` independently of the longer decoder pipeline. It must not be interpreted as corrected data or used as a latency-aligned decoder-response word. This historical behavior was preserved.

Hsiao uses 64 odd-weight data columns and the eight identity check columns. Encoder and syndrome equations are shared across the flat and hierarchical pair. The flat correction bit 0 matches syndrome `8'h07`; the hierarchical equivalent is `high_match[0] & low_match[7]`. Corrected data is a bitwise XOR mask; nonzero unmatched syndromes report uncorrectable input. Full mapped connectivity and cell histograms remain inspectable in the original synthesis JSON and the new mapped example.

## Byte identity and preservation

`baseline_manifest.json` hashes 189 selected existing source/evidence files and checks both original source contracts. Six unique checked source files match directly in Revision-2. Two unique files, the Hsiao v1 encoder and syndrome, differ from the recorded hashes; four check records reflect their inclusion in two contracts. Their current bytes are LF, and the recorded hashes exactly match CRLF representations of those bytes. The sealed Git commit contains the same LF bytes as the checkout. This is a diagnosed representation conflict, not an established functional change; it remains an exact-byte identity mismatch. No file was rewritten, no historical hash was updated, and no frozen manifest was resealed.

The Phase II package validator independently verifies that all 189 audited baseline files remain byte-identical to the initial Phase II inventory. New work is confined to `research/phase2`. Technology and tool identities, negative runs, unsupported results and full qualification waveforms are retained.
