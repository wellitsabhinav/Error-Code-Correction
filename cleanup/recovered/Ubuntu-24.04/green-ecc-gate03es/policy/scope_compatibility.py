"""Narrow additive-path compatibility for historical gate validators.

This adapter does not authorize changes inside any historical evidence tree.
It only recognizes separately named, explicitly registered additive gate paths;
byte identity of historical trees is enforced by Gate 03E-S manifests.
"""

from __future__ import annotations

from pathlib import PurePosixPath


REGISTERED_ADDITIVE_PREFIXES = (
    "docs/date2027/rigour_gate_03er/",
    "scripts/gate03er/",
    "tests/python/test_gate03er_reproducibility.py",
    "docs/date2027/rigour_gate_03es/",
    "scripts/gate03es/",
    "tests/python/test_gate03es_",
)

HISTORICAL_EVIDENCE_PREFIXES = (
    "docs/date2027/rigour_gate_01/",
    "docs/date2027/rigour_gate_02/",
    "docs/date2027/rigour_gate_03/",
    "docs/date2027/rigour_gate_03r/",
    "docs/date2027/rigour_gate_03e/",
)


def normalized_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        return ""
    return normalized


def is_registered_additive_path(path: str) -> bool:
    normalized = normalized_repo_path(path)
    return bool(normalized) and normalized.startswith(REGISTERED_ADDITIVE_PREFIXES)


def is_scope_path_allowed(path: str, historical_validator_allowlist: tuple[str, ...]) -> bool:
    normalized = normalized_repo_path(path)
    return bool(normalized) and (
        normalized.startswith(historical_validator_allowlist)
        or is_registered_additive_path(normalized)
    )
