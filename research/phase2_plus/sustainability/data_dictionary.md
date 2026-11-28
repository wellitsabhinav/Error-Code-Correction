# Sustainability inputs

`sources.csv` preserves original units, converted values, the reporting year,
publication and retrieval dates, inventory and scope, and the citation locator.
`technology_mapping.csv` records compatibility with the physical population.
The nominal 200 mm diameter is an engineering conversion of the 8-inch fab
class. Wafer edge, scribe lanes, functional yield, parent area and integration
utilization are scenario assumptions in `scenario_assumptions.yaml`. TSMC
reports a wafer product inventory. The scenario assumes this precedes
functional die yield. A source with already included die yield uses a distinct
model input and rejects another yield adjustment.

| Tier | Interpretation |
|---|---|
| A | Direct, matching technology and lifecycle boundary |
| B | Verifiable industrial category proxy or observed grid factor |
| C | Public academic model or parameter |
| D | Hypothetical sensitivity assumption |
| UNAVAILABLE | No compatible acquired value |

The paired DATE metric counts simultaneous independent encoder and decoder
transactions at the codec boundary. The SRAM metric covers ECC and wrapper
logic power at the retained E5 reporting boundary. SRAM idle is a measured
power over idle cycles, never a useful transaction. The DATE scenarios assume
equal zero incremental idle burden and expose the sensitivity to an unknown
idle difference. Whole-chip operational power, packaging, downstream burdens
and memory macro-internal power are outside the evaluated scope.

The scenario grid uses historical manufacturing categories and static eGRID
observations as alternative deployment settings. The two-interval sensitivity
uses the same published grid factors as hypothetical endpoints. Corporate
targets and product water data are context. The model keeps 2030/2035
product-wafer values unavailable.
