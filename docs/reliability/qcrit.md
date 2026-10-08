# Qcrit and SER qualification

`qcrit_loader.py` validates lookup tables, units, duplicate entries, and coordinates and supplies lookup/interpolation. Qcrit is charge in fC. An interpolated table value is not an experimentally qualified SRAM bitcell threshold.

`ser_model.ser_hazucha` implements `FIT_node=C*flux_rel*area_um2*exp(-Qcrit_fC/Qs_fC)`. Constants, flux reference, sensitive area, node, voltage, and temperature are calibration/model inputs. Preserve sources and units; capacity scaling supplies no missing physical calibration.

The routed population lacks qualified Qcrit/beam/fluence evidence, physical MBU probabilities, and a verified physical/logical map. Absolute SRAM SER/SDC/DUE/FIT and interleaver reliability remain blocked. Logical verification and sensitivity studies remain valid within their assumptions.

Inspect `python eccsim.py reliability report --help`. See [fault model](model.md) and [limitations](../limitations.md).
