"""Mide las aristas que `spec/CORE_v0.5.md` (borrador) afirma y que ningún caso del
corpus fija: la M4 generalizada, el léxico de V3, los bordes del iterando de V2, `for`
sobre `str` con su gemelo de forma idéntica, y P3 (identidad y nombres de la
especialización).

Corpus: 401–442 de `programs/conformance_v0.5/` cubren otras cosas. Aquí no se mide
cobertura del corpus sino las frases del borrador que hoy solo estaban en prosa, así
que la sonda lleva sus propios programas en el fuente y sus controles:

  1. M4 (misma versión que la raíz): matriz 2 × 4; solo las dos diagonales ejecutan.
  2. V3 (`for` reservada solo desde 0.5; `in` nunca reservada): cuatro cabeceras.
  3. V2 §4.3 (el iterando es un LUGAR): cuatro formas aceptadas, cuatro rechazadas.
  4. V2 §4.4 + V6 §7 (neutralidad de pasos **a forma constante**): cuatro programas
     que deben dar los mismos 24 pasos, más el control de la forma equivocada —el
     gemelo sin `let`, que da 20 y que la sonda reporta como trampa, no como fallo.
  5. P3: `program_sha256` no se mueve con la especialización y la traza muestra el
     nombre resuelto (`pad.2`), nunca la definición pelada.

Un PASS con el árbol sucio de código es `EVIDENCE_ONLY`, nunca gate de release.

    python3 tools/v05_spec_probe.py            # corre y reporta, no escribe
    python3 tools/v05_spec_probe.py --write    # sella en evidence/v05_spec/
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco.interp import run                                   # noqa: E402
from isyco.source import Bundle                                # noqa: E402

V05 = ROOT / "programs" / "conformance_v0.5"


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def dirty_codigo() -> bool:
    """Código, corpus o pruebas sin commitear ⇒ la corrida no puede ser gate de release."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return True
    for linea in out.splitlines():
        if not linea.strip():
            continue
        partes = [p.strip() for p in (linea[3:] if len(linea) > 3 else "").split("->")]
        if all(p.startswith("evidence/") for p in partes):
            continue
        return True
    return False


# --- 1. M4 generalizada --------------------------------------------------------------
MODULO = "{v}\npub fn di() -> i32 {{ return 7; }}\n"


def raiz(v: str) -> bytes:
    return (f"{v}\nimport linea;\nfn main() -> i32 {{ return linea.di(); }}\n").encode()


def matriz_m4():
    filas = []
    for vr in ("0.4", "0.5"):
        for vm in ("0.2", "0.3", "0.4", "0.5"):
            bundle = Bundle((("main.isy", raiz(f"isyco {vr}")),
                             ("linea.isy", MODULO.format(v=f"isyco {vm}").encode())))
            r, _ = run(bundle, [])
            filas.append({"raiz": vr, "modulo": vm, "status": r["status"], "code": r["code"],
                          "return": r["return"], "diagonal": vr == vm})
    return filas


# --- 2. léxico (V3) ------------------------------------------------------------------
LEXICO = [("0.4", "for", "isyco 0.4\nfn main() -> i32 { let for: i32 = 5; return for; }", 5),
          ("0.5", "for", "isyco 0.5\nfn main() -> i32 { let for: i32 = 5; return for; }", None),
          ("0.4", "in", "isyco 0.4\nfn main() -> i32 { let in: i32 = 5; return in; }", 5),
          ("0.5", "in", "isyco 0.5\nfn main() -> i32 { let in: i32 = 5; return in; }", 5)]


def matriz_lexico():
    filas = []
    for version, palabra, fuente, esperado in LEXICO:
        r, _ = run(fuente.encode(), [])
        filas.append({"cabecera": version, "identificador": palabra, "status": r["status"],
                      "code": r["code"], "return": r["return"], "predicho": esperado})
    return filas


# --- 3. el iterando es un lugar (V2 §4.3) --------------------------------------------
PRE = ("struct Q { ys: [i32; 2] }\n"
       "struct P { xs: [i32; 3], q: Q }\n"
       "fn id(a: [i32; 3]) -> [i32; 3] { return a; }\n")


def programa(cuerpo: str) -> bytes:
    return (f"isyco 0.5\n{PRE}fn main() -> i32 !emit {{ {cuerpo} return 0; }}").encode()


ITERANDO = [("for x in xs", 'let xs: [i32; 3] = [1,2,3]; for x in xs { emit x; }', ["1", "2", "3"]),
            ("for x in p.xs",
             'let p: P = P{xs:[1,2,3], q: Q{ys:[4,5]}}; for x in p.xs { emit x; }',
             ["1", "2", "3"]),
            ("for x in p.q.ys",
             'let p: P = P{xs:[1,2,3], q: Q{ys:[4,5]}}; for x in p.q.ys { emit x; }', ["4", "5"]),
            ("for x in xs[0]", 'let xs: [i32; 3] = [1,2,3]; for x in xs[0] { emit x; }', None),
            ("for x in id(xs)", 'let xs: [i32; 3] = [1,2,3]; for x in id(xs) { emit x; }', None),
            ("for x in (xs)", 'let xs: [i32; 3] = [1,2,3]; for x in (xs) { emit x; }', None),
            ("for x in [1,2,3]  [P2]", 'for x in [1,2,3] { emit x; }', None),
            ("for x con x visible",
             'let x: i32 = 9; let xs: [i32; 3] = [1,2,3]; for x in xs { emit x; }', "DUP"),
            ("for anidado",
             'let xs: [i32; 2] = [1,2]; for x in xs { for y in xs { emit x + y; } }',
             ["2", "3", "3", "4"]),
            ("continue en for (el incremento avanza)",
             'let xs: [i32; 3] = [1,2,3]; for x in xs { continue; emit x; }', []),
            ("foridx elegido fuera de los nombres del módulo",
             'let foridx0: i32 = 7; let xs: [i32; 2] = [1,2]; for x in xs { emit x + foridx0; }',
             ["8", "9"])]


def matriz_iterando():
    filas = []
    for nombre, cuerpo, esperado in ITERANDO:
        r, _ = run(programa(cuerpo), [])
        filas.append({"forma": nombre, "status": r["status"], "code": r["code"],
                      "emits": r["emits"], "predicho": esperado})
    return filas


# --- 4. `for` sobre str y la forma del gemelo (§4.4, §7) ------------------------------
CUATRO = {
    "A for / str<4>": ("isyco 0.5\nfn recorre(s: str<4>) -> i64 !emit { for c in s { emit c; }"
                       " return len(s); }\nfn main() -> i64 !emit { let t: str<4> = \"hola\";"
                       " return recorre(t); }"),
    "B while / str<4>": ("isyco 0.5\nfn recorre(s: str<4>) -> i64 !emit { let i: i64 = -1;"
                         " while i + 1 < len(s) { i = i + 1; let c: u8 = s[i]; emit c; }"
                         " return len(s); }\nfn main() -> i64 !emit { let t: str<4> = \"hola\";"
                         " return recorre(t); }"),
    "C while / str pelado (V6)": ("isyco 0.5\nfn recorre(s: str) -> i64 !emit { let i: i64 = -1;"
                                  " while i + 1 < len(s) { i = i + 1; let c: u8 = s[i]; emit c; }"
                                  " return len(s); }\nfn main() -> i64 !emit"
                                  " { let t: str<4> = \"hola\"; return recorre(t); }"),
    "D for / str pelado (V2+V6)": ("isyco 0.5\nfn recorre(s: str) -> i64 !emit { for c in s"
                                   " { emit c; } return len(s); }\nfn main() -> i64 !emit"
                                   " { let t: str<4> = \"hola\"; return recorre(t); }"),
    # control de forma: el mismo B sin el `let c` del cuerpo. Da OTROS pasos y la
    # diferencia no es el azúcar sino la forma — la trampa que ya cazó V6-bis.
    "Z while / str<4> SIN el let (forma distinta)": (
        "isyco 0.5\nfn recorre(s: str<4>) -> i64 !emit { let i: i64 = -1;"
        " while i + 1 < len(s) { i = i + 1; emit s[i]; } return len(s); }"
        "\nfn main() -> i64 !emit { let t: str<4> = \"hola\"; return recorre(t); }"),
}


def matriz_pasos():
    filas = []
    for nombre, fuente in CUATRO.items():
        r, _ = run(fuente.encode(), [])
        filas.append({"programa": nombre, "status": r["status"], "code": r["code"],
                      "emits": r["emits"], "return": r["return"], "steps": r["steps"]})
    return filas


# --- 5. P3: identidad y nombres de la especialización ---------------------------------
P3 = ("411_pad_dos_anchos", "417_junta_dos_contextuales", "420_recursion_contextual")


def matriz_p3():
    filas = []
    for nombre in P3:
        data = (V05 / f"{nombre}.isy").read_bytes()
        r, _ = run(data, [])
        filas.append({"caso": nombre, "sha_resultado": r["program_sha256"],
                      "sha_archivo": hashlib.sha256(data).hexdigest(),
                      "igual": r["program_sha256"] == hashlib.sha256(data).hexdigest()})
    r, filas_traza = run((V05 / "411_pad_dos_anchos.isy").read_bytes(), [], None, trace="stmt")
    nombres = sorted({f.get("fn") for f in filas_traza if f.get("fn")})
    return filas, nombres, {"status": r["status"], "emits": r["emits"], "steps": r["steps"]}


def main(argv: list[str]) -> int:
    write = "--write" in argv
    m4 = matriz_m4()
    lex = matriz_lexico()
    it = matriz_iterando()
    pasos = matriz_pasos()
    p3, nombres_traza, res411 = matriz_p3()

    sucio = dirty_codigo()
    rec = {"comando": " ".join(argv) or "v05_spec_probe.py",
           "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "git_head": git_head(), "arbol_sucio_codigo": sucio,
           "veredicto_arbol": "EVIDENCE_ONLY" if sucio else "RELEASE_GATE",
           "python": platform.python_version(),
           "corpus": str(V05.relative_to(ROOT)),
           "fuente_normativa": "spec/CORE_v0.5.md (BORRADOR) §0, §2, §4.3, §4.4, §7, §11"}
    documento = {"schema": "isyco.evidence/0.1",
                 "milestone": "Borrador CORE v0.5 — aristas normativas sin caso de corpus",
                 "receipt": rec, "m4": m4, "lexico": lex, "iterando": it,
                 "pasos_forma_constante": pasos, "p3": {"programas": p3,
                                                        "fn_en_traza_411": nombres_traza,
                                                        "resumen_411": res411}}

    lineas = [
        "Borrador CORE v0.5 — las aristas que el texto afirma y el corpus no fija",
        f"utc={rec['utc']}  git_head={rec['git_head']}  arbol={rec['veredicto_arbol']} "
        f"(sucio_codigo={rec['arbol_sucio_codigo']})",
        f"comando: {rec['comando']}   python={rec['python']}",
        "",
        "1) M4: todo modulo del programa tiene la MISMA version que la raiz",
    ]
    for fila in m4:
        lineas.append(f"   raiz={fila['raiz']}  modulo={fila['modulo']}  ->  "
                      f"{fila['status']}({fila['code']})  return={fila['return']}  "
                      f"diagonal={fila['diagonal']}")
    lineas += ["", "2) lexico (V3): `for` reservada solo desde 0.5; `in` nunca reservada"]
    for fila in lex:
        lineas.append(f"   {fila['cabecera']}: let {fila['identificador']}: i32 = 5  ->  "
                      f"{fila['status']}({fila['code']})  return={fila['return']}  "
                      f"predicho={fila['predicho']}")
    lineas += ["", "3) el iterando del `for` es un LUGAR (V2 §4.3), no una expresion"]
    for fila in it:
        lineas.append(f"   {fila['forma']:46s} -> {fila['status']}({fila['code']}) "
                      f"emits={fila['emits']}  predicho={fila['predicho']}")
    lineas += ["", "4) pasos a FORMA CONSTANTE (V2 §4.4 y V6 §7) — y el control de forma"]
    for fila in pasos:
        lineas.append(f"   {fila['programa']:44s} -> {fila['status']}({fila['code']}) "
                      f"pasos={fila['steps']}  emits={fila['emits']}  return={fila['return']}")
    lineas += ["", "5) P3: la especializacion no mueve program_sha256 y si se ve en la traza"]
    for fila in p3:
        lineas.append(f"   {fila['caso']:30s} sha_resultado==sha_archivo={fila['igual']}  "
                      f"{fila['sha_archivo'][:16]}")
    lineas.append(f"   fn en la traza de 411: {nombres_traza}   (la definicion pelada "
                  f"no aparece)")

    # ---- auto-falsación
    falsos = []
    for fila in m4:
        if fila["diagonal"] and (fila["status"], fila["return"]) != ("HALTED", "7"):
            falsos.append(f"M4: raiz {fila['raiz']} + modulo igual no ejecuta "
                          f"({fila['status']}({fila['code']}))")
        if not fila["diagonal"] and (fila["status"], fila["code"]) != \
                ("INVALID_PROGRAM", "VERSION_MISMATCH"):
            falsos.append(f"M4: raiz {fila['raiz']} + modulo {fila['modulo']} se acepta "
                          f"({fila['status']}): la regla dejaria mezclar familias")
    for fila in lex:
        if fila["predicho"] is None:
            if (fila["status"], fila["code"]) != ("INVALID_PROGRAM", "SYNTAX"):
                falsos.append(f"léxico: `{fila['identificador']}` con cabecera "
                              f"{fila['cabecera']} no es SYNTAX ({fila['status']})")
        elif (fila["status"], fila["return"]) != ("HALTED", str(fila["predicho"])):
            falsos.append(f"léxico: `let {fila['identificador']}` con {fila['cabecera']} "
                          f"da {fila['status']}({fila['code']}), se esperaba HALTED "
                          f"{fila['predicho']}")
    for fila in it:
        if fila["predicho"] == "DUP":
            if (fila["status"], fila["code"]) != ("INVALID_PROGRAM", "DUPLICATE_NAME"):
                falsos.append(f"iterando: {fila['forma']} no es DUPLICATE_NAME "
                              f"({fila['status']}({fila['code']}))")
        elif fila["predicho"] is None:
            if (fila["status"], fila["code"]) != ("INVALID_PROGRAM", "SYNTAX"):
                falsos.append(f"iterando: {fila['forma']} se acepta "
                              f"({fila['status']}) — el iterando dejó de ser un lugar")
        elif fila["status"] != "HALTED" or fila["emits"] != fila["predicho"]:
            falsos.append(f"iterando: {fila['forma']} da {fila['status']}({fila['code']}) "
                          f"emits={fila['emits']}, se esperaba HALTED {fila['predicho']}")
    buenos = [f for f in pasos if not f["programa"].startswith("Z ")]
    medidos = {f["programa"]: f["steps"] for f in buenos}
    if len(set(medidos.values())) != 1 or any(f["status"] != "HALTED" for f in buenos):
        falsos.append(f"pasos: los cuatro programas de forma idéntica no coinciden {medidos}")
    trampa = next(f for f in pasos if f["programa"].startswith("Z "))
    if trampa["steps"] == buenos[0]["steps"]:
        falsos.append("control de forma: el gemelo SIN `let` da los mismos pasos, así que "
                      "la comparación de pasos no distingue forma y el PASS no prueba nada")
    for fila in p3:
        if not fila["igual"]:
            falsos.append(f"P3: {fila['caso']} reporta otro program_sha256 que el del "
                          f"archivo — la especialización entró en la identidad")
    if any(re.fullmatch(r"pad", n) for n in nombres_traza):
        falsos.append(f"P3: la traza de 411 llama a la definición pelada ({nombres_traza})")
    if not any("." in n for n in nombres_traza):
        falsos.append(f"P3: la traza de 411 no muestra ninguna especialización "
                      f"({nombres_traza}) — el control es vacío")

    for mensaje in falsos:
        print(f"CONTROL FALSO: {mensaje}")
    if write and falsos:
        print("no se sella: hay controles falsos")
        return 1
    print("\n".join(lineas))
    if not write:
        return 0
    stamp = rec["utc"].replace(":", "").replace("-", "")
    destino = ROOT / "evidence" / "v05_spec"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"run_{stamp}.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (destino / f"run_{stamp}.json").write_text(
        json.dumps(documento, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    archivos = sorted(p for p in destino.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (destino / "SHA256SUMS.txt").write_text(
        "\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
                  for p in archivos) + "\n", encoding="utf-8")
    print(f"\nsellado en {destino.relative_to(ROOT)}/run_{stamp}.{{txt,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
