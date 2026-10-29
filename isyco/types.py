"""Tipos y aritmética exacta de v0.1 (spec §3).

Representación de valores en el intérprete:
- bool    -> bool de Python
- int<…>  -> int de Python dentro del rango del tipo
- dec<…>  -> int de Python m, con valor real m / 10**s
- [T; N]  -> list de Python (se copia en cada asignación y paso de parámetro)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from .errors import RuntimeFault


@dataclass(frozen=True)
class BoolT:
    def __str__(self) -> str:
        return "bool"


@dataclass(frozen=True)
class IntT:
    bits: int
    signed: bool
    ovf: str  # trap | wrap | sat

    @property
    def lo(self) -> int:
        return -(1 << (self.bits - 1)) if self.signed else 0

    @property
    def hi(self) -> int:
        return (1 << (self.bits - 1)) - 1 if self.signed else (1 << self.bits) - 1

    def __str__(self) -> str:
        return f"int<{self.bits},{'signed' if self.signed else 'unsigned'},{self.ovf}>"


@dataclass(frozen=True)
class DecT:
    p: int
    s: int
    rnd: str = "half_even"

    @property
    def max_m(self) -> int:
        return 10 ** self.p - 1

    def __str__(self) -> str:
        return f"dec<{self.p},{self.s},{self.rnd}>"


@dataclass(frozen=True)
class ArrT:
    elem: object
    n: int

    def __str__(self) -> str:
        return f"[{self.elem}; {self.n}]"


INT_ALIASES = {
    f"{'i' if signed else 'u'}{bits}": IntT(bits, signed, "trap")
    for bits in (8, 16, 32, 64) for signed in (True, False)
}


def is_numeric(t) -> bool:
    return isinstance(t, (IntT, DecT))


def is_scalar(t) -> bool:
    return isinstance(t, (BoolT, IntT, DecT))


# --- enteros -----------------------------------------------------------------

def int_fit(t: IntT, v: int, at: str | None) -> int:
    """Aplica la regla ovf del tipo al resultado matemático exacto v."""
    if t.lo <= v <= t.hi:
        return v
    if t.ovf == "trap":
        raise RuntimeFault("OVERFLOW", at)
    if t.ovf == "wrap":
        return (v - t.lo) % (1 << t.bits) + t.lo
    return t.hi if v > t.hi else t.lo


def int_trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


# --- decimales -----------------------------------------------------------------

def round_scaled(q: Fraction, mode: str, at: str | None) -> int:
    """Redondea q (ya multiplicado por 10**s) a entero con el modo dado."""
    if q.denominator == 1:
        return q.numerator
    if mode == "exact":
        raise RuntimeFault("INEXACT", at)
    if mode == "down":
        return int(q)  # int() de Fraction trunca hacia cero
    if mode == "half_up":
        n = abs(q)
        r = int(n + Fraction(1, 2))
        return r if q > 0 else -r
    # half_even
    n = q.numerator // q.denominator  # piso
    rest = q - n
    if rest > Fraction(1, 2):
        return n + 1
    if rest < Fraction(1, 2):
        return n
    return n if n % 2 == 0 else n + 1


def dec_fit(t: DecT, m: int, at: str | None) -> int:
    if abs(m) > t.max_m:
        raise RuntimeFault("OVERFLOW", at)
    return m


# --- conversiones (spec §3.6) ---------------------------------------------------

def cast(value, src, dst, at: str | None):
    if isinstance(src, IntT) and isinstance(dst, IntT):
        return int_fit(dst, value, at)
    if isinstance(src, IntT) and isinstance(dst, DecT):
        return dec_fit(dst, value * 10 ** dst.s, at)
    if isinstance(src, DecT) and isinstance(dst, IntT):
        return int_fit(dst, int(Fraction(value, 10 ** src.s)), at)
    if isinstance(src, DecT) and isinstance(dst, DecT):
        q = Fraction(value * 10 ** dst.s, 10 ** src.s)
        return dec_fit(dst, round_scaled(q, dst.rnd, at), at)
    raise AssertionError("el checker debió rechazar esta conversión")


# --- forma canónica (spec §10.1) ------------------------------------------------

def canonical(value, t):
    if isinstance(t, BoolT):
        return "true" if value else "false"
    if isinstance(t, IntT):
        return str(value)
    if isinstance(t, DecT):
        if t.s == 0:
            return str(value)
        digits = str(abs(value)).rjust(t.s + 1, "0")
        text = f"{digits[:-t.s]}.{digits[-t.s:]}"
        return f"-{text}" if value < 0 else text
    if isinstance(t, ArrT):
        return [canonical(v, t.elem) for v in value]
    raise AssertionError(t)


_INT_RE = re.compile(r"-?(0|[1-9][0-9]*)")


def parse_canonical(text, t):
    """Lee un valor de entrada en forma canónica; None si no lo es."""
    if isinstance(t, ArrT):
        if not isinstance(text, list) or len(text) != t.n:
            return None
        values = [parse_canonical(x, t.elem) for x in text]
        return None if any(v is None for v in values) else values
    if not isinstance(text, str):
        return None
    if isinstance(t, BoolT):
        return {"true": True, "false": False}.get(text)
    if isinstance(t, IntT):
        if not _INT_RE.fullmatch(text) or text == "-0":
            return None
        v = int(text)
        return v if t.lo <= v <= t.hi else None
    if isinstance(t, DecT):
        if t.s == 0:
            pattern = _INT_RE
        else:
            pattern = re.compile(r"-?(0|[1-9][0-9]*)\.[0-9]{%d}" % t.s)
        if not pattern.fullmatch(text):
            return None
        m = int(text.replace(".", ""))
        if m == 0 and text.startswith("-"):
            return None
        return m if abs(m) <= t.max_m else None
    return None
