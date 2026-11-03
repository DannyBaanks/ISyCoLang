# Estado de publicación — inventario de información sensible

**Fecha: 2026-11-03. Estado: NO PUBLICADO. Remoto: solo privado.**

Este documento existe porque se pidió empujar `eb4f0af` y abrir la PR del pase de docs.
Al mirar qué se iba con el push salió que la historia del repo lleva información
personal y de infraestructura interna que el estándar §21 pone del lado privado. Se
pidió sacarla antes de publicar; aquí está medido qué hay, dónde, y qué cuesta cada
salida. Ninguna cifra de abajo viene de memoria: todas son de comandos ejecutados
sobre este árbol el 2026-11-03 y se re-producen con los comandos citados.

## Decisión registrada

- 2026-10-28 — el repo es **privado**, sin licencia y sin remoto (el remoto creado ese
  día se borró a pedido de Danny).
- 2026-11-03 — Danny pide empujar y, delante del hallazgo §21, elige **remoto privado**
  (`DannyBaanks/ISyCoLang`) y dejar la publicación pública pendiente de esta limpieza.
- Consecuencia vinculante: mientras este documento diga que la limpieza no está hecha,
  **no se crea un remoto público ni se cambia la visibilidad** del privado.

## Qué hay y dónde

Historia: **131 commits** (`git rev-list --all --count`), **775 ficheros trackeados**
sobre `eb4f0af` (`git ls-files | wc -l`), una sola rama (`main`), cero tags, cero
ficheros borrados (`git log --all --diff-filter=D` sale vacío).

| # | qué | dónde | líneas | se puede limpiar |
|---|---|---|---|---|
| 1 | dirección de correo personal de Danny como **author y committer de los 131 commits** | metadata git, no el árbol | 131 | solo reescribiendo la historia |
| 2 | toolchain completo del host con ruta absoluta (`rustc 1.98.1`, `ghc`, `go 1.23.1`, `julia 1.11.3`, `zig 0.16.0`) | `evidence/inventory/toolchains_2026-10-28.txt` | 9 | no — fijado por `evidence/inventory/SHA256SUMS.txt` |
| 3 | raíz del monorepo (`…/ISyCo/workspace/assembly`) | `evidence/inventory/assembly_inventory_2026-10-29T000520Z.json` | 1 | no — fijado por el mismo `SHA256SUMS.txt` |
| 4 | ruta de instalación de Zig en el stderr crudo | `evidence/f5_harness/run_2026-11-02T233718Z_zig_build_stderr.txt` | 3 | no — fijado por `evidence/f5_harness/SHA256SUMS.txt` |
| 5 | ídem, dentro del recibo del gate | `evidence/f5_harness/run_2026-11-02T233718Z.json` | 2 | no — ídem |
| 6 | ídem, recibo del `FAIL` preservado | `evidence/backends/gate_2026-11-02T235456Z.json` | 4 | no — fijado por `evidence/backends/SHA256SUMS.txt` |
| 7 | ruta del monorepo hardcodeada en el tool | `tools/inventory_assembly.py:25` | 1 | **sí** — es código, no evidencia |

Puntos 2-6 son 19 líneas y 80 KB en total; los cinco están sellados y la regla de
`docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md` y de `AGENTS.md` es no reescribir
evidencia cruda. El punto 7 ya está corregido en este lote: la raíz se lee de
`ISYCO_ASSEMBLY` o de `~/Development/ISyCo/workspace/assembly`, y el valor resuelto es
el mismo de antes (medido con `python3 -c` sobre el módulo, y con `ISYCO_ASSEMBLY=/tmp/otra`).

El punto 1 no se cita con la dirección escrita aquí a propósito: se reproduce con
`git log --format='%an <%ae> | %cn <%ce>' | sort -u`. Copiarla en un doc sería
duplicar la fuga.

## Qué NO está (barrido con resultado negativo, que también es dato)

Los tres comandos, corridos hoy sobre el árbol, salen **vacíos**:

```text
git log --all -p -G"(ghp_|gho_|ghs_|github_pat_|BEGIN [A-Z ]*PRIVATE KEY|access_token|AWS_SECRET)"
git grep -hoE "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}" HEAD
git log --all --diff-filter=D --name-only
```

Ni credenciales, ni tokens, ni claves, ni correos dentro del árbol, ni ficheros
borrados que sigan vivos en la historia. Hostnames y `uname` tampoco aparecen; los
dos hits del patrón de IP (`3.1.2.0`, `21.0.12.1`) son números de versión, no
direcciones. Nada de `isyco/`, `spec/`, `programs/` ni `tests/` contiene rutas del
host.

## Las dos salidas que existen

**(R1) Empujar la cadena (131 commits) a un repo público.** Expone los 7 puntos tal
cual. La dirección del punto 1 queda en objetos inmutables: revocarla después exige
reescribir la historia y cambiar los 131 hashes, con lo que los `git_head` que citan
los recibos sellados y los docs (`b4b8873`, `14b19a9`, `026db0f`, `4b20744`, `6ebb00d`,
`2499fae`, `6c00225`, `66fe651`) dejan de resolver en el repo publicado. Aceptable solo
en remoto privado, que es donde está hoy.

**(R2) Exportación sin historia.** Un repo público nuevo con un único commit de un
árbol preparado, authored con la dirección noreply de GitHub, y con `evidence/` de por
medio:

1. quitar del árbol exportado `evidence/inventory/` (puntos 2 y 3) y publicar su
   SHA-256 para que la copia externa sea verificable — el estándar §21 deja el
   inventario del host del lado privado y `evidence/` del público, y esto es §21, no
   una excusa: el archivo lista compiladores y rutas de una máquina concreta.
2. recoser las referencias, que son cinco lugares verificables: la fila de contexto
   `docs/EVIDENCE_MATRIX.md:150`, el mapa de `README.md` (sección «Referencia del repositorio»)
   y sus «Gates y comandos avanzados», `ROADMAP.md:74`, la prosa del inventario
   `ROADMAP.md:420` y las dos filas de la claim table `ROADMAP.md:555-556` —estas dos
   dicen `DEMONSTRATED` y su evidencia pasa a ser una copia externa con hash publicado,
   que es lo que §21 permite pero no lo que un lector de GitHub puede verificar sin más.
   Y la regla 8 de `AGENTS.md`.
3. decidir qué se hace con los puntos 4-6, que sí son evidencia del idioma: son 9
   líneas con `~/.local/opt/zig-…`. §21 pone `evidence` del lado público, así que la
   opción por defecto es publicarlas; si se quieren fuera, el recibo deja de ser
   verificable byte a byte y hay que re-sellar, lo que abre un recibo nuevo (regla 7).
4. el commit exportado no es `eb4f0af`: la cadena autoritativa sigue viviendo en el
   remoto privado y en los bundles, y el repo público es una publicación, no el
   historial.

**Coste de R2**: el repo público no permite `git log` del desarrollo ni `bisect`, y
cualquier lectura externa de «en qué commit se cerró P4» se responde con el bundle, no
con el repo. **Beneficio**: nada de los 7 puntos sale al mundo, y los sellos no se
tocan.

## Estado de la limpieza

| paso | estado |
|---|---|
| punto 7 (path en el tool) | **hecho** el 2026-11-03 |
| inventario medido de 1-6 | **hecho** (este documento) |
| remoto privado con la cadena completa | **hecho** el 2026-11-03 (`origin`) |
| punto 1 (correo en metadata) | **abierto** — solo se resuelve eligiendo R1 o R2 |
| puntos 2-6 (19 líneas selladas) | **abierto** — ídem |
| repo público | **NO_DEMONSTRADO / no existe**: bloqueado hasta que Danny elija R1 o R2 |

Mientras los tres últimos renglones no estén cerrados, cualquier pedido de «publicar»
se responde primero con este documento y la elección de salida.
