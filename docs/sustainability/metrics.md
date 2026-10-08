# Existing metric formulas and normalization

These formulas document existing code without changing numerical behavior or fields. Legacy utilities do not override campaign qualification.

## ESII

`esii.compute_esii` uses FIT floor `f=1e-30`. Let `d=max(log10(max(F_base,0)+f)-log10(max(F_ecc,0)+f),0)` and `U_rel=d/(d+2)` with the code's safe-division stabilizer. `E=(E_dyn+E_leak+E_scrub)/3.6e6` is kWh; `C_total=I_grid*E+C_embodied` is kgCO2e. Define `U(x,h)=1/(1+max(x,0)/max(h,1e-12))`.

`ESII=clamp01(U_rel*(U(E,1 kWh)+U(C_total,1 kgCO2e))/2)`.

Weights are equal. Reliability half-saturation is 2 decades; burden scales are 1 kWh and 1 kg. These are policy constants. ESII in [0,1] is not a measured carbon-saving ratio.

## NESII

`normalise_esii` uses NumPy's 5th/95th percentiles over the supplied cohort and returns `100*(clip(x,p5,p95)-p5)/(p95-p5+1e-9)` plus anchors. Equal anchors give zero; an empty cohort yields no scores and NaN anchors. `scores.compute_scores` appends the evaluated scenario to its reference; without a reference the singleton NESII is zero. Record cohort/filtering/percentile convention.

## GREEN Score

`gs.compute_gs` uses `Sr=U_rel`, `Sc=U(carbon_kg,1 kg)`, `Sl=U(max(latency_ns-latency_base_ns,0),10 ns)`, `So=U(overhead_norm,0.25)`. Default weights `(R,C,L,O)=(0.6,0.25,0.1,0.05)`. Negative weights are clipped; unavailable carbon is excluded; positive active weights are renormalized. No active weights raises an error.

`GS=100*clamp01(exp(sum_j (w_j/sum(w_active))*log(max(S_j,1e-12))))`.

A three-weight call disables overhead. The log floor leaves a very small positive result at zero reliability utility. Absent carbon gives neutral `Sc` and legacy `total_kgCO2e=0`; that compatibility representation is not qualified zero carbon. Modern campaign records retain null/block states.

## EPC

`parse_telemetry.compute_epc` validates telemetry, sums XOR/AND toggles, estimates gate energy for node/voltage, and divides by summed `corr_events`: `EPC=E_estimated/correction_events`, J/event. Nonpositive counts raise `ValueError`. Energy per corrected bit requires a corrected-bit denominator; it coincides only for one-bit events. Macro, idle, leakage, and scrub energy are included only where producers/models explicitly declare them.

Use-phase carbon is `(E_use/3.6e6)*I_use`. Lifecycle scope, lifetime, yield, replacement, allocation, and manufacturing inventory need separate provenance. E5 logic energy does not supply missing macro energy or SKY130 inventory. See [sustainability](../sustainability-model.md) and [matrix policy](../matrix-optimization.md).
