# Figure requirement coverage

Nine evidence-grounded figure sets are available in PDF, SVG and PNG. All have source hashes and regeneration instructions in `figures/figure_manifest.json`. Unsupported plots were not filled with invented values.

| Requested figure | Available artifact | Status |
|---|---|---|
| 1 Actual architecture comparison | `01_pipeline_registers`, `02_hsiao_circuit_example`, `09_mapped_xor_example` | COMPLETE as RTL/mapped structure |
| 2 Explicit register placement | `01_pipeline_registers` | COMPLETE |
| 3 Three-way methodology | `03_estimator_contract` | COMPLETE as method contract; not results |
| 4 Energy across A/B/C | No qualified B/C energy | BLOCKED; `04_historical_paired_energy` is historical A only |
| 5 Estimation deviation | No C reference | BLOCKED |
| 6 Matched seed effects | `04_historical_paired_energy` | HISTORICAL ONLY |
| 7 Internal switching comparison | `07_synthetic_hazard` | SYNTHETIC ONLY; routed ECC comparison blocked |
| 8 Capacitance-weighted switching | No eligible capacitance/event join | BLOCKED |
| 9 Clock/sequential overhead | `05_historical_power_accounting` | HISTORICAL ONLY |
| 10 Workload activity vs energy | `08_workload_activity` | INPUT CHARACTERISTICS ONLY; energy blocked |
| 11 Error regime vs energy | Software conditions tabulated; no energy | BLOCKED |
| 12 Timing/area/energy/latency tradeoffs | `06_historical_tradeoffs` | HISTORICAL ONLY |

The pipeline, mapped-circuit and power-accounting previews were visually inspected. Labels have units and explicit evidence boundaries. Scientific plots use fixed interpretable axes; historical timing is labelled as a signed-slack estimate, not measured Fmax.
