"""ISyCoLang v0.1 — intérprete de referencia (semántica normativa: spec/CORE.md)."""
from .interp import DEFAULT_LIMITS, canonical_json, load, run

__all__ = ["DEFAULT_LIMITS", "canonical_json", "load", "run"]
