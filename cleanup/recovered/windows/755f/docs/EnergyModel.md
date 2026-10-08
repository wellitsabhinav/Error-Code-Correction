# Energy Model

This module provides a tiny energy estimation for each read operation in the
simulators. It multiplies the number of primitive gate evaluations by
technology-aware energy costs loaded from `tech_calib.json`. Gate counts scale
linearly with the ECC word size so wider codewords incur proportionally higher
dynamic energy.

## Calibration

`tech_calib.json` maps process node and voltage to per-gate energy figures for
XOR, AND and adder primitives. The loader performs piecewise linear
interpolation over this table so the estimate reflects the chosen technology and
supply voltage.

An optional explicit MUX term is available through `estimate_energy` and
`dynamic_energy_per_op`:

```
E = N_xor E_xor + N_and E_and + alpha_mux N_mux E_mux + E_other
```

`N_mux` is the number of equivalent 2:1 units and `E_mux` must be supplied
explicitly; the function raises an error instead of silently approximating a
MUX with XOR/AND energy. The repository's ECC-internal MUX lookup is an
illustrative assumption with no VDD dimension, not a standard-cell or silicon
characterization. `mux_leakage_power_w` provides a separate analytical
area-density leakage term for incremental MUX area.

The leakage model now accepts a process corner argument (`ss`, `tt`, `ff`) and
uses a gentler temperature coefficient, roughly doubling every 15 °C. This gives
a more realistic view of static power across operating conditions.

## Running the script

1. From the repository root, run the module with the number of parity bits and
   optionally the detected error count:

   ```bash
   python3 energy_model.py <parity_bits> [detected_errors]
   ```

   Example:

   ```bash
   python3 energy_model.py 8 1
   ```

   The command above estimates the energy to process eight parity bits when one
   error was detected.

2. The script prints a single line:

   ```
   Estimated energy per read: <value> J
   ```

   `<value>` is the estimated energy in joules, formatted in scientific notation.

This simple calculation helps gauge the energy impact of different error control
coding schemes during reads without running the full simulators.

## Typical Values from Literature

The calibration data includes energy measurements published for 28&nbsp;nm CMOS
processes, where an XOR gate consumes roughly 2&nbsp;pJ per operation and an AND
gate about 1&nbsp;pJ. These figures provide a reasonable baseline when evaluating
the simulators on common hardware.
