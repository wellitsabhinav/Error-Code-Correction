"""Carbon arithmetic in SI units with explicit scope and eligibility."""

from dataclasses import dataclass
import math


JOULES_PER_KWH = 3_600_000
SECONDS_PER_YEAR = 365.25 * 86_400


def nonnegative(value, field):
    if isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} must be finite and nonnegative")
    return value


def joules_to_kwh(joules):
    return nonnegative(joules, "energy in joules") / JOULES_PER_KWH


def pj_to_j(picojoules):
    return nonnegative(picojoules, "energy in picojoules") * 1e-12


def grams_to_kg(grams):
    return nonnegative(grams, "mass in grams") / 1000


def um2_to_mm2(area):
    return nonnegative(area, "area in square micrometres") * 1e-6


def wafer_area_mm2(diameter_mm, edge_mm=0):
    diameter = nonnegative(diameter_mm, "wafer diameter") - 2 * nonnegative(edge_mm, "edge exclusion")
    if diameter <= 0:
        raise ValueError("No usable wafer after edge exclusion")
    return math.pi * (diameter / 2) ** 2


@dataclass(frozen=True)
class Wafer:
    kg_per_wafer: float
    diameter_mm: float
    edge_mm: float
    scribe_mm: float
    die_yield: float | None
    burden_includes_die_yield: bool = False
    defects_per_mm2: float = 0
    aspect_ratio: float = 1

    def __post_init__(self):
        wafer_area_mm2(self.diameter_mm, self.edge_mm)
        nonnegative(self.kg_per_wafer, "wafer burden")
        nonnegative(self.scribe_mm, "scribe width")
        nonnegative(self.defects_per_mm2, "defect density")
        if nonnegative(self.aspect_ratio, "die aspect ratio") == 0:
            raise ValueError("Die aspect ratio is zero")
        if self.burden_includes_die_yield:
            if self.die_yield is not None or self.defects_per_mm2:
                raise ValueError("Die yield is already included in the source burden")
        elif self.die_yield is None or not 0 < self.die_yield <= 1:
            raise ValueError("An explicit die yield in (0,1] is required")

    def gross_dies(self, die_mm2):
        # Continuous edge-loss approximation. Use a layout map for integer
        # die-step effects at a specific wafer scale and stepping origin.
        if nonnegative(die_mm2, "die area") == 0:
            raise ValueError("Die area is zero")
        width = math.sqrt(die_mm2 * self.aspect_ratio) + self.scribe_mm
        height = math.sqrt(die_mm2 / self.aspect_ratio) + self.scribe_mm
        area = wafer_area_mm2(self.diameter_mm, self.edge_mm)
        gross = area / (width * height) - math.sqrt(area * math.pi / 2) * (1 / width + 1 / height)
        if gross < 1:
            raise ValueError("Continuous die-count approximation is outside its domain")
        return gross

    def die_kg(self, die_mm2):
        yield_fraction = 1.0 if self.burden_includes_die_yield else (
            self.die_yield * math.exp(-self.defects_per_mm2 * die_mm2)
        )
        if yield_fraction == 0:
            raise ValueError("Effective functional yield underflow")
        return self.kg_per_wafer / (self.gross_dies(die_mm2) * yield_fraction)


def embodied_kg(wafer, model, base_die_mm2, effective_ecc_mm2):
    """Standalone wafer allocation, without adding a second fab inventory."""
    if model not in {"fixed", "allocated", "marginal"}:
        raise ValueError(f"Unknown manufacturing boundary: {model}")
    if wafer is None or base_die_mm2 is None:
        return None
    if nonnegative(base_die_mm2, "parent die area") == 0:
        raise ValueError("Parent die area is zero")
    if model == "fixed":
        return wafer.die_kg(base_die_mm2)
    if effective_ecc_mm2 is None:
        return None
    nonnegative(effective_ecc_mm2, "effective ECC block area")
    if model == "marginal":
        return wafer.die_kg(base_die_mm2 + effective_ecc_mm2)
    if effective_ecc_mm2 > base_die_mm2:
        raise ValueError("Allocated block is larger than its containing die")
    return wafer.die_kg(base_die_mm2) * (effective_ecc_mm2 / base_die_mm2)


def act_area_kg(area_mm2, fab_kwh_per_cm2, fab_kg_per_kwh, process_kg_per_cm2, materials_kg_per_cm2, die_yield):
    """ACT Eq. 4 for fab and materials only, with area passed in mm²."""
    fab = nonnegative(fab_kwh_per_cm2, "fab electricity") * nonnegative(fab_kg_per_kwh, "fab grid intensity")
    per_cm2 = fab + nonnegative(process_kg_per_cm2, "process burden") + nonnegative(
        materials_kg_per_cm2, "material burden"
    )
    return act_cpa_kg(area_mm2, per_cm2, die_yield)


def act_cpa_kg(area_mm2, burden_kg_per_cm2_before_yield, die_yield):
    if not 0 < die_yield <= 1:
        raise ValueError("ACT yield must be in (0,1]")
    return (nonnegative(area_mm2, "die area") / 100
            * nonnegative(burden_kg_per_cm2_before_yield, "area carbon burden") / die_yield)


def normalized_mix(mix):
    if not mix or not math.isclose(math.fsum(nonnegative(x, op) for op, x in mix.items()), 1, abs_tol=1e-12,
                                    rel_tol=0):
        raise ValueError("Operation fractions must sum to one")
    return mix


@dataclass(frozen=True)
class Interval:
    seconds: float
    active_seconds: float
    grid_kg_per_kwh: float
    operation_counts: dict[str, float]

    def __post_init__(self):
        if nonnegative(self.seconds, "interval seconds") == 0:
            raise ValueError("Interval duration must be positive")
        if nonnegative(self.active_seconds, "active seconds") > self.seconds:
            raise ValueError("Active and idle windows overlap")
        nonnegative(self.grid_kg_per_kwh, "deployment grid")
        for operation, count in self.operation_counts.items():
            nonnegative(count, operation)
        if not self.active_seconds and any(self.operation_counts.values()):
            raise ValueError("Operations cannot complete outside the active window")

    def carbon_kg(self, energy_j, idle_w):
        components = []
        for operation, count in self.operation_counts.items():
            if count:
                value = energy_j.get(operation)
                if value is None:
                    return None
                components.append(count * nonnegative(value, operation))
        idle_seconds = self.seconds - self.active_seconds
        if idle_seconds:
            if idle_w is None:
                return None
            components.append(idle_seconds * nonnegative(idle_w, "idle power"))
        return joules_to_kwh(math.fsum(components)) * self.grid_kg_per_kwh


def deployment(seconds, utilization, active_per_second, grid_kg_per_kwh, mix):
    if nonnegative(utilization, "utilization") > 1:
        raise ValueError("Utilization exceeds 1")
    active = seconds * utilization
    count = active * nonnegative(active_per_second, "service rate")
    return Interval(seconds, active, grid_kg_per_kwh,
                    {operation: count * fraction for operation, fraction in normalized_mix(mix).items()})


def operational_kg(intervals, energy_j, idle_w):
    burdens = [interval.carbon_kg(energy_j, idle_w) for interval in intervals]
    return None if None in burdens else math.fsum(burdens)


@dataclass(frozen=True)
class Payback:
    status: str
    crossings: tuple[float, ...] = ()
    ties: tuple[tuple[float, float], ...] = ()


def break_even_operations(delta_emb_kg, saved_j_per_operation, grid_kg_per_kwh):
    if None in (delta_emb_kg, saved_j_per_operation, grid_kg_per_kwh):
        return Payback("UNAVAILABLE")
    grid = nonnegative(grid_kg_per_kwh, "deployment grid")
    if not math.isfinite(delta_emb_kg) or not math.isfinite(saved_j_per_operation):
        raise ValueError("Carbon or energy difference is nonfinite")
    saving = saved_j_per_operation * grid / JOULES_PER_KWH
    if delta_emb_kg == saving == 0:
        return Payback("TIE")
    if delta_emb_kg <= 0 <= saving:
        return Payback("IMMEDIATE_CANDIDATE")
    if saving <= 0 <= delta_emb_kg:
        return Payback("IMMEDIATE_REFERENCE")
    crossing = delta_emb_kg / saving
    return Payback("CANDIDATE_PAYBACK" if saving > 0 else "REFERENCE_PAYBACK", (crossing,))


def time_crossings(delta_emb_kg, intervals):
    """Intervals are (duration, candidate-minus-reference kg in that interval)."""
    intervals = tuple(intervals)
    if delta_emb_kg is None or any(delta is None for _, delta in intervals):
        return Payback("UNAVAILABLE")
    if not math.isfinite(delta_emb_kg):
        raise ValueError("Initial carbon difference is nonfinite")
    time = 0.0
    delta = delta_emb_kg
    crossings, ties = [], []
    signs = {math.copysign(1, delta)} if delta else set()
    for duration, change in intervals:
        if nonnegative(duration, "interval duration") == 0 or not math.isfinite(change):
            raise ValueError("Positive duration and finite interval difference required")
        end_delta = delta + change
        if not delta and not end_delta:
            ties.append((time, time + duration))
        elif change and (delta * end_delta <= 0):
            root = time - delta * duration / change
            if not crossings or not math.isclose(root, crossings[-1], rel_tol=1e-13, abs_tol=1e-12):
                crossings.append(root)
        time += duration
        delta = end_delta
        if delta:
            signs.add(math.copysign(1, delta))
    if len(signs) == 2:
        status = "CROSSES_IN_LIFETIME"
    elif not signs:
        status = "TIE"
    elif signs == {-1}:
        status = "CANDIDATE_LOWER_OR_EQUAL"
    else:
        status = "REFERENCE_LOWER_OR_EQUAL"
    return Payback(status, tuple(crossings), tuple(ties))


@dataclass(frozen=True)
class Service:
    contract: str
    capacity_words: int
    latency_cycles: int
    rate_hz: float
    area_um2: float | None
    route_complete: bool
    setup_ns: float | None
    hold_ns: float | None
    hold_violations: int | None

    def eligible(self, *, contract, capacity_words, max_latency, min_rate, max_area=None):
        return (
            self.contract == contract and self.capacity_words == capacity_words
            and self.latency_cycles <= max_latency and self.rate_hz >= min_rate
            and self.route_complete and self.setup_ns is not None and self.hold_ns is not None
            and self.setup_ns >= 0 and self.hold_ns >= 0 and self.hold_violations == 0
            and (max_area is None or (self.area_um2 is not None and 0 <= self.area_um2 <= max_area))
        )


def minimax_regret(costs):
    """Accept a rectangular scenario matrix for a common eligible candidate set."""
    if not costs or not costs[0]:
        raise ValueError("Scenario and candidate sets must be nonempty")
    candidates = sorted(costs[0])
    if any(sorted(row) != candidates for row in costs):
        raise ValueError("Candidates differ across deployment scenarios")
    regrets = {candidate: [] for candidate in candidates}
    for row in costs:
        for value in row.values():
            nonnegative(value, "lifecycle carbon")
        minimum = min(row.values())
        for candidate in candidates:
            regrets[candidate].append(row[candidate] - minimum)
    worst = {candidate: max(values) for candidate, values in regrets.items()}
    winners = tuple(candidate for candidate in candidates if worst[candidate] == min(worst.values()))
    return winners, worst, regrets


def pareto_front(costs):
    """Return all candidates that are undominated in the same ordered objectives."""
    if not costs or not next(iter(costs.values()), ()):
        raise ValueError("Pareto comparison requires objectives")
    size = len(next(iter(costs.values())))
    if any(len(values) != size or not all(math.isfinite(val) for val in values) for values in costs.values()):
        raise ValueError("Pareto objectives are missing or incompatible")
    return tuple(sorted(
        name for name, values in costs.items()
        if not any(
            all(other_value <= own_value for other_value, own_value in zip(other, values)) and other != values
            for other in costs.values()
        )
    ))
