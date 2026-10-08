# ECC specifications and decoder policies

Codes, concrete encoder/decoder implementations, and deployment architectures are separate identities. This table is transcribed from the cleanup-base registry. Declared correctable weights still require the implementation evidence gate; a family label is insufficient.

| Specification | n/k | Declared correctable weights | Exact distance |
|---|---:|---|---:|
| `hsiao-secded-72-64-v1` | 72/64 | 1 | 4 |
| `extended-hamming-secded-72-64-v1` | 72/64 | 1 | 4 |
| `repository-cyclic-63-51-v1` | 63/51 | 1 | 2 |
| `primitive-bch-63-51-t2-v1` | 63/51 | 1, 2 | 5 |
| `shortened-bch-71-64-t1-v1` | 71/64 | 1 | 3 |
| `shortened-bch-78-64-t2-v1` | 78/64 | 1, 2 | 5 |
| `shortened-bch-85-64-t3-v1` | 85/64 | 1, 2, 3 | not exact |
| `odd-column-secded-4-8` | 8/4 | 1 | 4 |
| `forge-hotspot-8-4-v1` | 8/4 | 1 | 4 |
| `odd-column-secded-64-72` | 72/64 | 1 | 4 |
| `forge-spatial-hotspot-72-64-v1` | 72/64 | 1 | 3 |
| `safeforge-robust-72-64-mapping-v1` | 72/64 | none declared | 4 |
| `safeforge-robust-8-4-v1` | 8/4 | none declared | 3 |
| `forge-sram-portfolio-72-64-v1-geometry-filtered-joint` | 72/64 | 1 | 4 |
| `forge-sram-portfolio-72-64-v1-spatial-hotspot-joint` | 72/64 | 1 | 4 |

Extended-Hamming/Hsiao (72,64) provide SECDED inside verified universes. Primitive BCH (63,51,t=2) differs from the historical degree-12 cyclic candidate with exact distance 2. Shortened BCH variants have bounded t=1,2,3; errors beyond the bound may be detected or miscorrected. Adjacent double/triple policies need their own counterexample/outcome records.

SEC-DAEC's counterexample excludes it from matched physical comparison. Incomplete archived syndrome tables can fail eligibility despite valid mathematical codes. There are 17 implementations and 15 selectable after verification. Run `python eccsim.py ecc list` for current identities/statuses.

See [campaign ECC status](../ecc-architectures.md), [catalogue](../ECC_CATALOGUE.md), and [verification methodology](../VERIFICATION_METHODOLOGY.md).
