# Architecture and module boundaries

The framework connects SRAM/workload inputs, logical fault response, implementation evidence, energy/carbon models, and explicit decision policies. Public interfaces remain in `eccsim.py` and root model/selector modules. Cleanup preserves imports, default CLI output, and JSON/CSV fields.

| Module | Responsibility | Boundary |
|---|---|---|
| `green_ecc_phy/` | Registry, adapters, exact verification, comparison | Guarantees bind a decoder and declared mask universe |
| `codeforge/` | Binary linear-code construction and synthesis | A constructed code is not automatically a qualified decoder |
| `architecture/` | Deployment, transitions, scheduling, DSE | Workload/service assumptions stay explicit |
| `ser_model.py`, `qcrit_loader.py`, `mbu.py` | Conditional event/burst assumptions | No measured physical FIT population |
| Energy/carbon/score modules | Cost and utility calculations | Arithmetic does not qualify missing evidence |
| `ecc_selector.py` | Baseline deterministic decision | Policy-specific recommendation |
| `ml/` | Optional prediction/fallback | Preserves the baseline and constraints |
| `campaigns/` | Hashes, run identity, tool pins, summaries, failures | Frozen records retain original semantics |

See [main architecture](../architecture.md), [experiment pipeline](../experiment-pipeline.md), [evidence model](../evidence-model.md), and the [README flow](../../README.md).
