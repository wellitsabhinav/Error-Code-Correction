# P2-G00 readiness: BLOCKED

The synthetic IOPATH experiment passed in the explicit two-cell assembly with matching nanosecond time units. The complete production gate did not pass. No routed ECC delay-aware power experiment was admitted.

| Acceptance item | Outcome | Evidence |
|---|---|---|
| Baseline preserved | PASS for the 189 audited files | `baseline_manifest.json`; read-only package validator |
| Existing identities verified | PARTIAL | Two unique Hsiao CRLF/LF conflicts; missing DATE physical archives |
| Simulator capability audit | COMPLETE, limitations found | Three retained Linux probe sets and native failure logs |
| Synthetic observable hazard | PASS, bounded assembly only | `raw/qualification_final/results.json` and full VCDs |
| Matching full routed timing models | BLOCKED | Two-cell assembly cannot qualify all mapped ECC cells or their timing checks |
| INTERCONNECT | FAIL on installed Icarus 12.0 stable | Default probe gives no wire-delay hazard; `-ginterconnect` is rejected |
| Timing checks | FAIL on tested setup/hold/width probes | Deliberate violations leave `NOTIFIER=0`; no diagnostic |
| Cross-unit SDF handling | FAIL on tested ps-SDF/ns-cell case | No usable settled output in the 5–49 ns observation window |
| Full annotation and power-import coverage | UNAVAILABLE | No matching DATE routed V/SDF/SPEF bundle |
| Parser and RTL smoke | PASS within tested scope | 13 Phase II tests pass, one symlink test skipped because host privilege is unavailable; four architectures × 100 completed RTL operations |

## Executed synthetic experiment

An input fans out through two `sky130_fd_sc_hd__buf_1` instances, reconverging at `sky130_fd_sc_hd__xor2_1`. Artificial controlled delays are fast 0.1/0.2/0.3 ns, slow 1/2/3 ns, and XOR 0.05/0.1/0.15 ns for min/typ/max. Two input changes occur at 10 and 30 ns. The measured window is [5,49) ns at 1 ps resolution. Expected settled output is zero throughout; a nonzero-duration high pulse following each simultaneous logical-path change is the synthetic hazard criterion.

| Run | Output binary transitions | High hazard width | Unknown time in valid final window |
|---|---:|---:|---:|
| Zero delay | 0 | none | 0 ps |
| IOPATH minimum | 4 | 900 ps, twice | 0 ps |
| IOPATH typical | 4 | 1800 ps, twice | 0 ps |
| IOPATH maximum | 4 | 2700 ps, twice | 0 ps |
| Narrow-path difference | 0 | 50 ps input-path skew not observed at output | 0 ps |

The typical waveform rises at 10,300 ps and falls at 12,100 ps, then repeats at 30,300 and 32,100 ps. A separate complete-event oracle agrees with the streaming parser: four edges, 3,600 ps high occupancy, and two high hazards. The parser's three generic inter-edge pulse segments include an 18,200 ps low interval; that low interval is not counted as a glitch. Alias signals share one accumulator and are not double-counted.

The 50 ps skew experiment uses a 100 ps XOR delay and produces no output edge, demonstrating observable pulse filtering under this setup. These are simulator observations with controlled delays, not cell characterization or measured physical glitch suppression.

## Negative controls and model assembly

The minimal public SkyWater source is pinned to commit `ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1`. Its wrapper/base files do not automatically include the separate specify fragments. The unassembled negative control parses SDF but reports four unmatched ModPath entries and produces no annotated hazard. The local assembly inserts the corresponding upstream specify fragment into each size wrapper, preserves its upstream functional base module, and records the resulting hashes. No production library identity or full-cell qualification is inferred from that assembly.

The deliberately wrong `u_fast` instance name generates a hierarchy warning while the process still exits zero and the output still has four transitions, now with a 2,000 ps high pulse. Therefore neither exit status nor event count alone establishes correct annotation. Exact pulse timing, known-state occupancy, expected arc identity and annotation diagnostics are necessary controls.

The first Linux experiment expressed delays in ps while the cell models use ns. It exits zero but does not settle within the planned window. The consistent-unit variant fixes only this synthetic condition; no general SDF unit-conversion support is claimed. Full routed SDF constructs cannot be inventoried until the matching physical bundle is recovered; the retained Revision-2 archive member manifest contains no SDF.

The native development Icarus driver has additional failures: its installed path contains a space, and the discovered alternate native prefix produces compilation access violations (exit 3221225477). Those attempts remain in `raw/simulator-qualification` and its command journal. The successful probe uses the already extracted Ubuntu Icarus 12.0 stable package through the existing `AutonomousEDA` WSL distribution. No simulator was installed.

## Required recovery

Recover the exact Revision-2 and breadth archive members by their existing hashes, resolve the two source-byte representations explicitly without rewriting frozen evidence, and qualify a simulator/model combination that applies the needed interconnect, conditional paths and timing checks. Generate SDF from the recovered implementation and matching Liberty/SPEF identities, then test per-arc annotation and VCD-to-OpenSTA coverage on 100 and 1,000 completed operations. Production jobs remain blocked until these conditions pass.
