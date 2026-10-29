"""Fuente de un programa: bytes (un archivo) o un Bundle (archivo principal + módulos).

CORE v0.4 §2: un programa es su archivo principal más los módulos que importa.
El frontend recibe un Bundle con todos los archivos ya leídos, así la ejecución
nunca toca el disco a medio camino y el programa entero tiene identidad fija.
Un Bundle es inmutable y hasheable, para que las cachés por programa funcionen
igual que con bytes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Bundle:
    files: tuple            # ((ruta relativa con "/", bytes), …) ordenado por ruta
    main: str = "main.isy"

    def get(self, path: str) -> bytes | None:
        for rel, data in self.files:
            if rel == path:
                return data
        return None

    @property
    def main_bytes(self) -> bytes:
        data = self.get(self.main)
        assert data is not None, self.main
        return data

    @classmethod
    def from_path(cls, main: Path, max_files: int = 4096) -> "Bundle":
        """Lee el archivo principal y todos los .isy bajo su carpeta (P1: los imports
        se resuelven relativos a ella). Solo los que se importen forman parte del
        programa; el resultado lista esos en `modules` (P6)."""
        main = Path(main)
        root = main.parent
        files = {main.name: main.read_bytes()}
        for path in sorted(root.rglob("*.isy")):
            rel = path.relative_to(root).as_posix()
            if rel not in files and path.is_file():
                if len(files) >= max_files:
                    raise ValueError(f"más de {max_files} archivos .isy bajo {root}")
                files[rel] = path.read_bytes()
        return cls(tuple(sorted(files.items())), main.name)


def main_bytes(source) -> bytes:
    return source.main_bytes if isinstance(source, Bundle) else source


def program_sha256(source) -> str:
    """CORE v0.4 P6: sigue siendo el hash del archivo principal."""
    return hashlib.sha256(main_bytes(source)).hexdigest()
