"""Capa compartida de los gates: cabecera de git, sello, árbol, SHA-256 y sellado.

Por qué existe: `backend_gate`, `c_gate`, `ir_gate` y `run_conformance` repetían cada uno su
`git_head()`, su formato de sello y su escritura del recibo, y los cuatro dejaban el JSON al
final de la corrida — abortar a mitad no dejaba evidencia. Aquí viven la cabecera, el sello,
el veredicto de conformidad y el `finally` que sella, para que la durabilidad no dependa de
que cada herramienta recuerde implementarla.

Las sondas (`tools/v05_*_probe.py`) conservan deliberadamente su copia: un cambio aquí no
puede reescribir el instrumento con el que se midió un claim ya sellado.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: Los tests y las sondas redirigen la evidencia con esta perilla (tests/test_evidence.py ya
#: la honraba); no es un ajuste para el operador: sin ella, una corrida de prueba destruye
#: el registro del gate.
EVIDENCE = Path(os.environ.get("ISYCO_EVIDENCE_ROOT") or ROOT / "evidence")
STAMP = "%Y-%m-%dT%H%M%SZ"


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def stamp() -> str:
    """Sello UTC de inicio de corrida: se calcula ANTES del trabajo, no al escribir."""
    return datetime.now(timezone.utc).strftime(STAMP)


def dirty_codigo() -> bool:
    """Código, corpus o pruebas sin commitear ⇒ la corrida no puede ser gate de release.

    Regla de las sondas (`v05_p4_probe.py`), aquí como campo del recibo: deja de ser una
    promesa de procedimiento y pasa a poder leerse en el JSON.
    """
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


def arbol() -> dict:
    """Los dos campos de procedencia del árbol, calculados al inicio de la corrida."""
    sucio = dirty_codigo()
    return {"arbol_sucio_codigo": sucio,
            "veredicto_arbol": "EVIDENCE_ONLY" if sucio else "RELEASE_GATE"}


def sums(destino: Path) -> int:
    """Rehace `SHA256SUMS.txt` del directorio con nombres pelados (se excluye a sí mismo).

    Nombres pelados porque así se verifica: `(cd evidence/<tema> && sha256sum -c SHA256SUMS.txt)`.
    """
    archivos = sorted(p for p in destino.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (destino / "SHA256SUMS.txt").write_text(
        "\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
                  for p in archivos) + "\n", encoding="utf-8")
    return len(archivos)


class Tee:
    """Duplica stdout: lo que ve el operador es byte a byte lo que se sella."""

    def __init__(self):
        self._buf = io.StringIO()

    def write(self, texto: str) -> int:
        sys.__stdout__.write(texto)
        self._buf.write(texto)
        return len(texto)

    def flush(self) -> None:
        sys.__stdout__.flush()

    @property
    def texto(self) -> str:
        return self._buf.getvalue()


class captura_stdout:
    """`with captura_stdout() as t:` — imprime normal y guarda la transcripción para sellarla."""

    def __enter__(self) -> Tee:
        self._tee = Tee()
        self._anterior = sys.stdout
        sys.stdout = self._tee
        return self._tee

    def __exit__(self, *exc) -> bool:
        sys.stdout.flush()
        sys.stdout = self._anterior
        return False


def es_conforme(e: dict) -> bool:
    """Un backend es conforme solo si ninguna pierna registró un fallo del instrumento.

    `failures` y `diffs` siguen siendo estrictamente divergencia semántica; la lista hermana
    `harness` es lo que murió en el toolchain o en el arnés. Plegarla aquí es lo que hace que
    un crash no pueda heredar un verde: `tests/test_evidence.py` ya afirma `conformant`.

    Las piernas se leen con `in`/`.get` porque una pierna abortada ANTES de correr se escribe
    `{"not_run": true}` y no tiene campos numéricos: eso es no-conforme por definición, no un
    cero que pasaría la comparación. Un `sabotage` vacío sigue siendo conforme: la cláusula del
    spec es "cada sabotaje declarado es detectado", y vacía es la afirmación cuando no hay
    ninguno, como en el gate de hoy.
    """
    if not e.get("completado"):
        return False
    if any(k not in e for k in ("corpus", "difftest", "does_the_work", "sabotage")):
        return False
    c, d, s = e["corpus"], e["difftest"], e.get("difftest_str", {})
    return (not c["failures"] and not c.get("harness", [])
            and not d["diffs"] and not d.get("harness", [])
            and not s.get("diff_count") and not s.get("harness", [])
            and e["does_the_work"]["ok"] and not e["does_the_work"].get("harness", [])
            and all(r["detected"] and not r.get("harness", []) for r in e["sabotage"].values()))


def sellar(report: dict, salidas: str | None, destino: Path, nombre: str) -> dict:
    """Escribe `<nombre>.json`, su stdout crudo y rehace los SHA256SUMS del directorio.

    Se niega a pisar un recibo existente: "nunca sobrescribe" era una frase del docstring y
    valía lo que valiera la memoria del que corriera el gate dos veces en el mismo segundo.
    Devuelve `{out, sha256, sumados}` para que la herramienta imprima su recibo igual que hoy.
    """
    destino.mkdir(parents=True, exist_ok=True)
    out = destino / f"{nombre}.json"
    if out.exists():
        raise FileExistsError(f"el recibo {out} ya existe: dos corridas en el mismo segundo "
                              f"o una ruta reutilizada (nunca se sobrescribe evidencia)")
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    out.write_text(payload, encoding="utf-8")
    if salidas is not None:
        (destino / f"{nombre}_stdout.txt").write_text(salidas, encoding="utf-8")
    ruta = str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out)
    return {"out": ruta, "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "sumados": sums(destino)}
