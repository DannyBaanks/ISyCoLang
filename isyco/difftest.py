"""Diferencial por tipo numérico: referencia vs un backend, en valores frontera.

Para cada tipo numérico T genera UN programa que elige la operación por un
argumento `op`, y lo ejecuta con muchas parejas (a, b): mínimos, máximos,
vecinos de cero, empates de redondeo y valores aleatorios con semilla fija.
Compara status, code, emits, return y steps.
"""
from __future__ import annotations

import random

from .interp import run
from .types import DecT, IntT, canonical

INT_TYPES = [IntT(bits, signed, ovf) for bits in (8, 16, 32, 64)
             for signed in (True, False) for ovf in ("trap", "wrap", "sat")]
DEC_TYPES = [DecT(18, 0, "half_even"), DecT(18, 2, "half_even"), DecT(18, 2, "half_up"),
             DecT(9, 4, "down"), DecT(4, 2, "exact"), DecT(18, 18, "half_even"),
             DecT(1, 0, "half_up"), DecT(5, 5, "exact")]
CAST_TARGETS = ["int<8, signed, wrap>", "int<16, unsigned, sat>", "i64", "u32",
                "dec<18,4>", "dec<6,2,half_up>", "dec<3,0,exact>", "dec<10,1,down>"]
COMPARED = ("status", "code", "emits", "return", "steps")


def src_type(t) -> str:
    if isinstance(t, IntT):
        return f"int<{t.bits}, {'signed' if t.signed else 'unsigned'}, {t.ovf}>"
    return f"dec<{t.p},{t.s},{t.rnd}>"


def ops_for(t) -> list[str]:
    ops = ["a + b", "a - b", "a * b", "a / b", "-a", "a < b", "a == b"]
    if isinstance(t, IntT):
        ops.append("a % b")
    ops += [f"a as {target}" for target in CAST_TARGETS]
    return ops


def program_for(t) -> bytes:
    ops = ops_for(t)
    branches = "\n    ".join(
        f"{'if' if i == 0 else '} else if'} op == {i} {{ emit {expr};" for i, expr in enumerate(ops))
    return (f"isyco 0.1\nfn main(op: i32, a: {src_type(t)}, b: {src_type(t)}) !emit {{\n"
            f"    {branches}\n    }}\n}}\n").encode()


def values_for(t, rng: random.Random, extra: int) -> list[int]:
    """Valores crudos (decimales escalados) interesantes para el tipo."""
    if isinstance(t, IntT):
        lo, hi = t.lo, t.hi
        base = {lo, lo + 1, hi - 1, hi, 0, 1, 2, 3, 7, 10, hi // 2, hi // 2 + 1}
        if t.signed:
            base |= {-1, -2, -3, -7, -10, lo // 2}
        base |= {rng.randint(lo, hi) for _ in range(extra)}
        return sorted(v for v in base if lo <= v <= hi)
    top = t.max_m
    half = 5 * 10 ** (t.s - 1) if t.s > 0 else 0
    base = {top, -top, 0, 1, -1, 2, -2, 3, top - 1, -(top - 1), top // 2, -(top // 2)}
    if half:
        base |= {half, -half, 3 * half, -3 * half, half + 1, -(half + 1), 15 * 10 ** max(t.s - 2, 0)}
    base |= {rng.randint(-top, top) for _ in range(extra)}
    return sorted(v for v in base if -top <= v <= top)


def forced_pairs(t) -> list[tuple[int, int]]:
    """Parejas que siempre se prueban: fronteras y empates de redondeo exactos."""
    if isinstance(t, IntT):
        pairs = [(t.lo, t.hi), (t.hi, t.hi), (t.lo, t.lo), (t.hi, 1), (0, 0), (1, 0)]
        if t.signed:
            pairs += [(t.lo, -1), (-7, 2), (7, -2), (-7, -2)]
        return pairs
    one = 10 ** t.s                    # el valor 1 escalado
    two = 2 * one
    pairs = [(t.max_m, t.max_m), (-t.max_m, t.max_m), (0, 0), (1, 0)]
    if two <= t.max_m:
        # m / 2 con m impar: el cociente cae justo en medio de dos unidades.
        pairs += [(m, two) for m in (1, 3, 5, -1, -3, -5) if abs(m) <= t.max_m]
    if t.s > 0:
        half = 5 * 10 ** (t.s - 1)     # 0.5
        # 0.5 * (m unidades mínimas) = m/2 unidades: empate si m es impar.
        pairs += [(half, m) for m in (1, 3, -1, -3)]
    return [(a, b) for a, b in pairs if abs(a) <= t.max_m and abs(b) <= t.max_m]


def cases_for(t, pairs: int, seed: int):
    """[(op, a, b)] con a y b ya en forma canónica."""
    rng = random.Random(f"{seed}:{t}")
    values = values_for(t, rng, extra=4)
    combos = [(a, b) for a in values for b in values]
    rng.shuffle(combos)
    chosen = forced_pairs(t) + combos[:pairs]
    out = []
    for op in range(len(ops_for(t))):
        for a, b in chosen:
            out.append((op, canonical(a, t), canonical(b, t)))
    return out


def compare(executor, pairs: int = 40, seed: int = 20261028, types=None) -> dict:
    """executor(programa, input) -> (resultado, traza). Devuelve resumen + diferencias."""
    report = {"seed": seed, "pairs_per_op": pairs, "types": [], "runs": 0, "diffs": []}
    for t in types or (INT_TYPES + DEC_TYPES):
        program = program_for(t)
        count = 0
        for op, a, b in cases_for(t, pairs, seed):
            inputs = [str(op), a, b]
            ref, _ = run(program, inputs)
            got, _ = executor(program, inputs)
            count += 1
            want = {k: ref[k] for k in COMPARED}
            have = {k: got.get(k) for k in COMPARED}
            if want != have or got.get("backend_stderr"):
                report["diffs"].append({"type": str(t), "op": ops_for(t)[op], "input": inputs,
                                        "reference": want, "backend": have,
                                        "stderr": got.get("backend_stderr")})
        report["types"].append({"type": str(t), "runs": count})
        report["runs"] += count
    return report


# --- strings (CORE v0.3) -----------------------------------------------------------

STR_CAST_TARGETS = ["int<8, signed, wrap>", "int<8, unsigned, sat>", "u8", "i64", "u64",
                    "int<64, signed, wrap>", "int<64, unsigned, wrap>", "int<16, signed, sat>",
                    "dec<6,2>", "dec<18,0>", "dec<18,18>", "dec<3,1,exact>", "bool"]
STR_OPS = ["a + b", "CTX", "a < b", "a == b", "a >= b", "len(a)", "a[i]", "slice(a, i, j)",
           "chr(i)", "i as str<3>", "d as str<5>", "(i < j) as str<4>", "a as str<3>"] \
    + [f"a as {target}" for target in STR_CAST_TARGETS]
BIG = "123456789012345678901234567890123456789012345"
STR_POOL = ["", "0", "-0", "05", "7", "-7", "-128", "127", "128", "255", "256", "-129", "300",
            "-300", "32767", "32768", "-32769", "18446744073709551615", "18446744073709551616",
            "-9223372036854775808", "9223372036854775807", "9223372036854775808",
            "-9223372036854775809", "340282366920938463463374607431768211457", BIG, "-" + BIG,
            "1.5", "2.50", "-2.50", "-0.00", "0.05", "0.00", "12.5", "99.9", "-99.9", "100.0",
            "9999.99", "-9999.99", "10000.00", "0." + "1" * 18, "-0." + "9" * 18, "1." + "0" * 18,
            "999999999999999999", "1000000000000000000", "true", "false", "True", "abc", "ab",
            "abd", "a\nb", "a\"b\\", "a\tb", "Z", "zz", "~" * 12, " ", "- 5", "+5", "5 ", "1e3"]


def str_program() -> bytes:
    branches = []
    for k, expr in enumerate(STR_OPS):
        head = "if" if k == 0 else "} else if"
        if expr == "CTX":   # concatenación con contexto: revisa contra str<16> (S3)
            branches.append(f"{head} op == {k} {{ let c: str<16> = a + b; emit c;")
        else:
            branches.append(f"{head} op == {k} {{ emit {expr};")
    body = "\n    ".join(branches)
    return (f"isyco 0.3\nfn main(op: i32, a: str<64>, b: str<8>, i: i64, j: i64, d: dec<6,2>) !emit {{\n"
            f"    {body}\n    }}\n}}\n").encode()


def str_cases(per_op: int, seed: int):
    rng = random.Random(f"{seed}:str")
    short = [x for x in STR_POOL if len(x) <= 8]
    ints = [-2, -1, 0, 1, 2, 3, 5, 7, 9, 10, 31, 32, 64, 65, 126, 127, 128, 255, 1000, -1000]
    decs = ["0.00", "-0.05", "12.50", "-9999.99", "9999.99", "100.00", "-100.00", "1.00"]
    out = []
    for op in range(len(STR_OPS)):
        chosen = set()
        if op >= STR_OPS.index("a as str<3>"):           # casts desde str: todo el pool
            chosen |= {(a, "", 0, 0, "0.00") for a in STR_POOL}
        positional = STR_OPS[op] in ("a[i]", "slice(a, i, j)")
        while len(chosen) < per_op * (3 if positional else 1) \
                + (len(STR_POOL) if op >= STR_OPS.index("a as str<3>") else 0):
            a = rng.choice(STR_POOL)
            if positional:   # índices alrededor de len(a): dentro, en el borde y fuera
                i, j = rng.randint(-1, len(a) + 1), rng.randint(-1, len(a) + 1)
            else:
                i, j = rng.choice(ints), rng.choice(ints)
            chosen.add((a, rng.choice(short), i, j, rng.choice(decs)))
        out += [(op, *c) for c in sorted(chosen)]
    return out


def compare_str(executor, per_op: int = 12, seed: int = 20261029) -> dict:
    """Diferencial de strings: concatenación, comparación, len/índice/slice/chr y casts."""
    program = str_program()
    report = {"seed": seed, "per_op": per_op, "runs": 0, "diffs": []}
    for op, a, b, i, j, d in str_cases(per_op, seed):
        inputs = [str(op), a, b, str(i), str(j), d]
        ref, _ = run(program, inputs)
        got, _ = executor(program, inputs)
        report["runs"] += 1
        want = {k: ref[k] for k in COMPARED}
        have = {k: got.get(k) for k in COMPARED}
        if want != have or got.get("backend_stderr"):
            report["diffs"].append({"op": STR_OPS[op], "input": inputs, "reference": want,
                                    "backend": have, "stderr": got.get("backend_stderr")})
    return report
