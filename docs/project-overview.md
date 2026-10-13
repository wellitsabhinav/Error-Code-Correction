# GREENS project overview

GREENS studies how to choose SRAM protection hardware using qualified evidence. Extended Hamming, Hsiao, and BCH names describe mathematical protection; concrete decoders and memory interfaces determine latency and physical cost. Source-equivalent protection can still lead to different mapped cells, placement, routing, timing, switching, and energy.

An SRAM designer first declares the service needed for W1/W2 errors, verifies the exact implementation, checks route/setup/hold at the intended constraint, and measures the intended operation mix. Lifecycle decisions follow only when every operand shares the intended boundary. Missing evidence produces an unavailable decision.

The [ISCAS artifact](../experiments/iscas/README.md) connects admitted implementation pairs to frozen data, claim derivations, tables, and figures in one or two clicks. The [results guide](results.md) also describes separate temporal and structural controls. The broader registry contains software and experimental entries that are not all admitted to the physical comparison.

Research origin: IIIT-Delhi, VICAS Lab. Developed by [Abhinav Choudhary](https://orcid.org/0009-0001-4892-5438) under the guidance of Dr. Anuj Grover. Institutional endorsement is not asserted.

Read [methodology](methodology.md), [architecture](architecture.md), [reproduction](../experiments/iscas/reproduction.md), and [limitations](limitations.md). The existing MIT license applies to repository software; upstream technology/macro material retains its own terms.
