"""Un solo sitio fija qué versiones soporta el frontend y qué reglas trae cada una.

`spec/CORE_v0.5_propuesta.md` §7 midió diez sitios con la versión escrita literal en
el código y ninguno se activaba con una versión mayor: declarar `0.5` sin ayuda
aqui dejaba enlazando programas modulares como si no tuvieran `import`, sin error.
Aquí la relación es monotónica por orden de SUPPORTED, así que `0.5` hereda las
familias de `0.3` y `0.4` automáticamente y una versión desconocida no trae ninguna
(fail-closed: `has` es False, y el parser rechaza la cabecera antes de eso).

Una familia es un conjunto de reglas, no una versión: `v03` trae `str` y `struct`,
`v04` los módulos, `v05` las decisiones de CORE v0.5 aprobadas.
"""
from __future__ import annotations

SUPPORTED = ("0.1", "0.2", "0.3", "0.4", "0.5")

#: familia -> primera versión que la trae
INTRODUCED = {"v02": "0.2", "v03": "0.3", "v04": "0.4", "v05": "0.5"}


def has(version: str, family: str) -> bool:
    """¿`version` trae la familia de reglas `family`?"""
    if version not in SUPPORTED:
        return False
    return SUPPORTED.index(version) >= SUPPORTED.index(INTRODUCED[family])
