# Architecture-aware GREENS design-space exploration

## Scope and validation boundary

This flow is an extensible, technology-portable, scenario-general layer over
the existing selector. It does not replace or silently alter the legacy CLI.
The shipped study has analytical reliability and exact logical-resource
accounting, but its legacy ECC area/latency values are projected and its
adaptive physical PPA is uncharacterized. No 14 nm synthesis, silicon
measurement, or PVT characterization is claimed.

## Deployment modes and hardware topologies

Deployment mode and topology are different decisions:

| Deployment mode | Instantiated selection hardware | Mode state | Migration |
|---|---|---|---|
| Design-time fixed | One selected engine; no selection MUX | None | Never |
| Boot-time/bank configurable | Parallel, gated-parallel, or shared datapath | Protected register/metadata | Not charged as a recurring access cost |
| Runtime adaptive | Configurable datapath and controller | Protected bank/page/epoch metadata | Charged and safely sequenced |

The topology report compares a fixed engine, parallel engines, gated parallel
engines, and a shared/reconfigurable datapath. Exact engine and MUX counts do
not imply that physical area is characterized.

## Storage and MUX model

Candidates are concrete `(n,k)` configurations belonging to an ECC family. A
logical word of `k_logical` bits occupies
`ceil(k_logical/k_i) * n_i` physical bits. A configurable bank uses a fixed
`n_max` container equal to the largest candidate footprint; unused positions
are reported as padding and reduce capacity efficiency.

For `M` selectable inputs of width `b`, the default pruned balanced tree uses:

```text
d_mux(M) = ceil(log2(M))                         (zero for M=1)
N_2:1(b,M) = b(M-1)                              pruned
N_2:1,padded(b,M) = b(2^ceil(log2(M)) - 1)       complete tree
N_mux,total = sum over selected paths N_2:1(b_p,M_p)
```

The modeled paths are encoded-codeword selection, decoded-data selection, and
status/syndrome selection. A shared datapath additionally has an input-routing
path. For the shipped five-mode, 64-bit example with a 128-bit container and a
four-bit status path, the pruned configured fabric is
`128*4 + 64*4 + 4*4 = 784` 2:1 cells with maximum depth three.

When an exact-PVT cell record is available:

```text
A_mux = sum(N_p * A_2:1) + A_route
t_mux,p = d_p * t_2:1(V,T,node) + t_wire,p
E_mux,p = N_p * alpha * C_switched * V^2
P_leak,mux = N_total * V * I_leak(V,T)
```

`alpha` is the expected transition probability per MUX cell per operation.
The energy convention is `alpha*C*V^2`; no extra one-half factor is applied.
Characterization is matched only at the exact node, voltage, temperature, and
process corner. There is no silent interpolation or node scaling. Synthesized
records take precedence over analytical records at the same PVT.

For parallel engines, characterized area is the sum of encoder/decoder engines
plus MUX, controller, and metadata area. Gated engines separately charge a
configurable fraction of inactive leakage and glitch energy. The read critical
path is memory read, optional routing, decode, data/status MUX, controller, and
metadata; the write path is controller/metadata, encode, codeword MUX, and
memory write. If any physical term is missing, the total stays `null` rather
than mixing characterized and invented values.

## Metadata, reliability, and transitions

Runtime mode identity needs `ceil(log2(M))` bits. The example triplicates each
bit, storing nine bits for five modes. An illegal value and a metadata vote
failure force the configured safe fallback. With optional independent terms:

```text
P_system_fail = 1 - (1-P_ECC)(1-P_mux)(1-P_controller)(1-P_metadata)
```

Disabled terms are omitted, not treated as proven zero. The independence
assumption is a tractable approximation and is reported in every result.

Runtime transitions quiesce the target region, decode with the old mode,
encode and write with the new mode, verify, and only then commit protected
metadata. The model reports migrated words, temporary capacity, total latency,
and:

```text
E_reconfig = N_migrated * (E_read/decode,old + E_encode/write,new) + E_control
```

The legacy energy record cannot separate read/decode from encode/write, so its
current migration term is explicitly marked as a per-access proxy.

## Carbon accounting

Operational carbon uses explicit units:

```text
C_op[kgCO2e] = CI[kgCO2e/kWh] * E_lifetime[J] / 3.6e6
```

Input in grams per kWh is explicitly converted to kilograms. Embodied-carbon
inputs expose effective area, manufacturing intensity per square centimetre,
yield allocation, die allocation, packaging allocation, number of amortized
systems, and source. Results separate base system carbon, incremental
operational carbon, incremental embodied carbon, absolute system carbon, and
amortized incremental carbon per access. With no sourced manufacturing input,
incremental embodied carbon remains `null`.

## Decision procedure

The default decision sequence is:

1. Filter hard reliability, latency, energy, area, capacity, carbon, and policy constraints.
2. Enumerate the exact Pareto set over every fully available objective.
3. Apply declared non-negative preference weights to normalized costs.
4. Report runner-up, baseline regret, Monte Carlo confidence, and sensitivity.

Exact enumeration is transparent and has `O(S*C^2)` time and `O(S*C)` result
storage for `S` scenarios and `C` feasible configurations. The revision script
also emits a host-dependent synthetic scaling benchmark. The retained legacy
non-dominated-sort implementation is tested against exact enumeration on a
tractable subset; it is not represented as a genuine evolutionary search.

ESII is a bounded product of a log-risk-reduction utility and a weighted
energy/carbon burden utility. NESII is a winsorized monotone normalization of
ESII within its reference set, so identical ESII/NESII rankings are expected,
not independent validation. GREEN Score adds a latency utility and can differ.
All are monotone only with their stated directions and fixed reference bounds.
The architecture flow therefore uses constraints, Pareto filtering, and a
declared preference function as primary; it keeps the three scores as an
ablation with rank correlations and a component-wise-dominance check.

## Extension interfaces

`architecture.types.CandidateRegistry` accepts new configurations without a
central-selector edit. `architecture.plugins` defines registries/protocols for
fault distributions, workloads, technology/PVT, carbon traces, and selection
policies. `architecture.providers.HardwareMetricProvider` is the common ECC
metric interface; `MuxCharacterizationProvider` imports exact-PVT analytical,
simulation, synthesis, or measurement records.

## Reproduction

```bash
python3 scripts/run_revision_study.py
```

Inputs are validated against `schemas/architecture-dse-config.schema.json`.
Outputs include JSON/CSV data, an SVG figure, a hash manifest, deployment
policy, register map, and generated SystemVerilog package. The configuration,
fixed random seed, source labels, tool boundary, and limitations travel with
the result.

