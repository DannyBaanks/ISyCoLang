"""Backend COBOL: ISY-IR v0.1 (núcleo numérico) -> GnuCOBOL -> binario nativo.

Ola 2 de F5 (spec/BACKEND.md §6), segunda implementación independiente del
dominio numérico: aritmética zoned DISPLAY (decimal de punto fijo, E22), con
`DIVIDE ... GIVING ... REMAINDER` truncado hacia cero (igual que la
referencia) y redondeo propio en `isy_rdiv`. `str` y `struct` (isy-ir/0.2,
CORE v0.3) se declaran NO implementadas: un caso del corpus que los use
responde UNSUPPORTED, nunca una aproximación.

Contrato del binario generado: igual que los nativos (ISY_BACKEND/1 §3), con
tres salvedades de GnuCOBOL 3.1 encontradas por sondas (evidence en las
pruebas de tests/test_backends.py) y respetadas en la traducción:

1. `cobc` 3.1 no trae `FUNCTION ARGUMENT-VALUE`: los argumentos entran por
   STDIN como una línea hexadecimal (el wrapper del "binario" la produce) y
   el programa la decodifica con `ORD`/`CHAR` y separador X"01".
2. La multiplicación zoned es exacta solo hasta 38 dígitos de producto:
   `u64 * u64` (39) se calcula por miembros de 32 bits.
3. Todo argumento de llamada se pasa como ITEM (lvalue): pasar una expresión
   hace que GnuCOBOL 3.1 lea basura. Los parámetros se copian a
   LOCAL-STORAGE en la entrada (semántica por valor, CORE §3.2).
4. Cada función IR se compila como subprograma `IS RECURSIVE` invocado con
   CALL y el resultado como último argumento por referencia: una FUNCTION-ID
   recursiva de GnuCOBOL 3.1.2 devuelve 0 (sonda), y sin RECURSIVE el
   LOCAL-STORAGE es estático y las llamadas anidadas pisan los marcos.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .base import ALL_FEATURES, V03_FEATURES, Backend
from ..ir import ty_from_json
from ..types import ArrT, BoolT, DecT, IntT, StrT, StructT, parse_canonical

SABOTAGES = ("half_even_as_half_up", "div_floor")
OVF_CODE = {"trap": 0, "wrap": 1, "sat": 2}
# Núcleo numérico de v0.1: bool, arreglos, llamadas, recursión, while, emit.
FEATURES = ALL_FEATURES - V03_FEATURES

RUNTIME = r"""       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-PUT-INT.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-U PIC 9(20).
       01 PS-BUF PIC X(20).
       01 PS-P PIC 99.
       01 PS-D PIC 9.
       01 PS-S2 PIC 99.
       01 PS-STARTED PIC 9.
       01 PS-FROM PIC 99.
       01 PS-LF PIC X VALUE X"0A".
       LINKAGE SECTION.
       01 LS-PFX PIC X(2).
       01 LS-VAL PIC S9(20).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-PFX LS-VAL RETURNING PS-RET.
           DISPLAY LS-PFX WITH NO ADVANCING.
           MOVE 0 TO PS-U.
           IF LS-VAL < 0
               DISPLAY "-" WITH NO ADVANCING
               COMPUTE PS-U = 0 - LS-VAL
           ELSE
               MOVE LS-VAL TO PS-U
           END-IF.
           IF PS-U = 0
               DISPLAY "0" WITH NO ADVANCING
           ELSE
               MOVE SPACES TO PS-BUF
               MOVE 20 TO PS-P
               PERFORM 20 TIMES
                   DIVIDE PS-U BY 10 GIVING PS-U REMAINDER PS-D
                   MOVE FUNCTION CHAR(PS-D + 49) TO PS-BUF(PS-P:1)
                   COMPUTE PS-P = PS-P - 1
               END-PERFORM
               MOVE 21 TO PS-FROM
               MOVE 0 TO PS-STARTED
               PERFORM VARYING PS-S2 FROM 1 BY 1 UNTIL PS-S2 > 20
                   IF PS-STARTED = 0 AND PS-BUF(PS-S2:1) NOT = "0"
                       MOVE PS-S2 TO PS-FROM
                       MOVE 1 TO PS-STARTED
                   END-IF
               END-PERFORM
               DISPLAY PS-BUF(PS-FROM:21 - PS-FROM) WITH NO ADVANCING
           END-IF.
           DISPLAY PS-LF WITH NO ADVANCING.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-PUT-INT.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-PUT-DEC.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-U PIC 9(20).
       01 PS-BUF PIC X(20).
       01 PS-P PIC 99.
       01 PS-D PIC 9.
       01 PS-S2 PIC 99.
       01 PS-STARTED PIC 9.
       01 PS-FROM PIC 99.
       01 PS-CUT PIC 99.
       01 PS-SC PIC 99.
       01 PS-LF PIC X VALUE X"0A".
       LINKAGE SECTION.
       01 LS-PFX PIC X(2).
       01 LS-VAL PIC S9(20).
       01 LS-SCALE PIC 9(2).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-PFX LS-VAL LS-SCALE RETURNING PS-RET.
           DISPLAY LS-PFX WITH NO ADVANCING.
           MOVE 0 TO PS-U.
           IF LS-VAL < 0
               DISPLAY "-" WITH NO ADVANCING
               COMPUTE PS-U = 0 - LS-VAL
           ELSE
               MOVE LS-VAL TO PS-U
           END-IF.
           MOVE LS-SCALE TO PS-SC.
           COMPUTE PS-CUT = 20 - PS-SC.
           MOVE SPACES TO PS-BUF.
           MOVE 20 TO PS-P.
           PERFORM 20 TIMES
               DIVIDE PS-U BY 10 GIVING PS-U REMAINDER PS-D
               MOVE FUNCTION CHAR(PS-D + 49) TO PS-BUF(PS-P:1)
               COMPUTE PS-P = PS-P - 1
           END-PERFORM.
           MOVE PS-CUT TO PS-FROM.
           MOVE 0 TO PS-STARTED.
           PERFORM VARYING PS-S2 FROM 1 BY 1 UNTIL PS-S2 > PS-CUT
               IF PS-STARTED = 0 AND PS-BUF(PS-S2:1) NOT = "0"
                   MOVE PS-S2 TO PS-FROM
                   MOVE 1 TO PS-STARTED
               END-IF
           END-PERFORM.
           DISPLAY PS-BUF(PS-FROM:PS-CUT + 1 - PS-FROM) WITH NO ADVANCING.
           IF PS-SC > 0
               DISPLAY "." WITH NO ADVANCING
               DISPLAY PS-BUF(PS-CUT + 1:PS-SC) WITH NO ADVANCING
           END-IF.
           DISPLAY PS-LF WITH NO ADVANCING.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-PUT-DEC.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-PUT-BOOL.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-LF PIC X VALUE X"0A".
       LINKAGE SECTION.
       01 LS-PFX PIC X(2).
       01 LS-VAL PIC 9.
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-PFX LS-VAL RETURNING PS-RET.
           DISPLAY LS-PFX WITH NO ADVANCING.
           IF LS-VAL = 1
               DISPLAY "true" WITH NO ADVANCING
           ELSE
               DISPLAY "false" WITH NO ADVANCING
           END-IF.
           DISPLAY PS-LF WITH NO ADVANCING.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-PUT-BOOL.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-EMIT-INT.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-END,
           FUNCTION ISY-PUT-INT.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-XS PIC X(16).
       01 PS-XC PIC X(24).
       01 PS-PFX PIC X(2) VALUE "E ".
       LINKAGE SECTION.
       01 LS-EMITS PIC S9(18).
       01 LS-MAXEMITS PIC S9(18).
       01 LS-STEPS PIC S9(18).
       01 LS-VAL PIC S9(20).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-EMITS LS-MAXEMITS LS-STEPS LS-VAL
           RETURNING PS-RET.
           IF LS-EMITS >= LS-MAXEMITS
               MOVE "LIMIT_REACHED" TO PS-XS
               MOVE "max_emits" TO PS-XC
               MOVE ISY-END(LS-STEPS, PS-XS, PS-XC) TO PS-RET
               STOP RUN
           END-IF.
           ADD 1 TO LS-EMITS.
           MOVE ISY-PUT-INT(PS-PFX, LS-VAL) TO PS-RET.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-EMIT-INT.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-EMIT-DEC.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-END,
           FUNCTION ISY-PUT-DEC.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-XS PIC X(16).
       01 PS-XC PIC X(24).
       01 PS-PFX PIC X(2) VALUE "E ".
       01 PS-SC PIC 9(2).
       LINKAGE SECTION.
       01 LS-EMITS PIC S9(18).
       01 LS-MAXEMITS PIC S9(18).
       01 LS-STEPS PIC S9(18).
       01 LS-VAL PIC S9(20).
       01 LS-SCALE PIC 9(2).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-EMITS LS-MAXEMITS LS-STEPS LS-VAL LS-SCALE
           RETURNING PS-RET.
           IF LS-EMITS >= LS-MAXEMITS
               MOVE "LIMIT_REACHED" TO PS-XS
               MOVE "max_emits" TO PS-XC
               MOVE ISY-END(LS-STEPS, PS-XS, PS-XC) TO PS-RET
               STOP RUN
           END-IF.
           ADD 1 TO LS-EMITS.
           MOVE LS-SCALE TO PS-SC.
           MOVE ISY-PUT-DEC(PS-PFX, LS-VAL, PS-SC) TO PS-RET.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-EMIT-DEC.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-EMIT-BOOL.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-END,
           FUNCTION ISY-PUT-BOOL.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-XS PIC X(16).
       01 PS-XC PIC X(24).
       01 PS-PFX PIC X(2) VALUE "E ".
       LINKAGE SECTION.
       01 LS-EMITS PIC S9(18).
       01 LS-MAXEMITS PIC S9(18).
       01 LS-STEPS PIC S9(18).
       01 LS-VAL PIC 9.
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-EMITS LS-MAXEMITS LS-STEPS LS-VAL
           RETURNING PS-RET.
           IF LS-EMITS >= LS-MAXEMITS
               MOVE "LIMIT_REACHED" TO PS-XS
               MOVE "max_emits" TO PS-XC
               MOVE ISY-END(LS-STEPS, PS-XS, PS-XC) TO PS-RET
               STOP RUN
           END-IF.
           ADD 1 TO LS-EMITS.
           MOVE ISY-PUT-BOOL(PS-PFX, LS-VAL) TO PS-RET.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-EMIT-BOOL.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-TICK.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-END.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-XS PIC X(16).
       01 PS-XC PIC X(24).
       LINKAGE SECTION.
       01 LS-STEPS PIC S9(18).
       01 LS-MAXSTEPS PIC S9(18).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-STEPS LS-MAXSTEPS RETURNING PS-RET.
           ADD 1 TO LS-STEPS.
           IF LS-STEPS > LS-MAXSTEPS
               MOVE "LIMIT_REACHED" TO PS-XS
               MOVE "max_steps" TO PS-XC
               MOVE ISY-END(LS-STEPS, PS-XS, PS-XC) TO PS-RET
               STOP RUN
           END-IF.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-TICK.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-ENTER.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-END.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-XS PIC X(16).
       01 PS-XC PIC X(24).
       LINKAGE SECTION.
       01 LS-STEPS PIC S9(18).
       01 LS-MAXSTEPS PIC S9(18).
       01 LS-DEPTH PIC S9(18).
       01 LS-MAXDEPTH PIC S9(18).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-STEPS LS-MAXSTEPS LS-DEPTH LS-MAXDEPTH
           RETURNING PS-RET.
           ADD 1 TO LS-STEPS.
           IF LS-STEPS > LS-MAXSTEPS
               MOVE "LIMIT_REACHED" TO PS-XS
               MOVE "max_steps" TO PS-XC
               MOVE ISY-END(LS-STEPS, PS-XS, PS-XC) TO PS-RET
               STOP RUN
           END-IF.
           IF LS-DEPTH + 1 > LS-MAXDEPTH
               MOVE "LIMIT_REACHED" TO PS-XS
               MOVE "max_call_depth" TO PS-XC
               MOVE ISY-END(LS-STEPS, PS-XS, PS-XC) TO PS-RET
               STOP RUN
           END-IF.
           ADD 1 TO LS-DEPTH.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-ENTER.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-LEAVE.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       LINKAGE SECTION.
       01 LS-DEPTH PIC S9(18).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-DEPTH RETURNING PS-RET.
           SUBTRACT 1 FROM LS-DEPTH.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-LEAVE.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-END.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-U PIC 9(20).
       01 PS-BUF PIC X(20).
       01 PS-P PIC 99.
       01 PS-D PIC 9.
       01 PS-S2 PIC 99.
       01 PS-STARTED PIC 9.
       01 PS-FROM PIC 99.
       01 PS-LF PIC X VALUE X"0A".
       LINKAGE SECTION.
       01 LS-STEPS PIC S9(18).
       01 LS-XS PIC X(16).
       01 LS-XC PIC X(24).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-STEPS LS-XS LS-XC RETURNING PS-RET.
           DISPLAY "X " WITH NO ADVANCING.
           DISPLAY FUNCTION TRIM(LS-XS) WITH NO ADVANCING.
           DISPLAY " " WITH NO ADVANCING.
           IF LS-XC = SPACES
               DISPLAY "-" WITH NO ADVANCING
           ELSE
               DISPLAY FUNCTION TRIM(LS-XC) WITH NO ADVANCING
           END-IF.
           DISPLAY " " WITH NO ADVANCING.
           MOVE 0 TO PS-U.
           IF LS-STEPS < 0
               DISPLAY "-" WITH NO ADVANCING
               COMPUTE PS-U = 0 - LS-STEPS
           ELSE
               MOVE LS-STEPS TO PS-U
           END-IF.
           IF PS-U = 0
               DISPLAY "0" WITH NO ADVANCING
           ELSE
               MOVE SPACES TO PS-BUF
               MOVE 20 TO PS-P
               PERFORM 20 TIMES
                   DIVIDE PS-U BY 10 GIVING PS-U REMAINDER PS-D
                   MOVE FUNCTION CHAR(PS-D + 49) TO PS-BUF(PS-P:1)
                   COMPUTE PS-P = PS-P - 1
               END-PERFORM
               MOVE 21 TO PS-FROM
               MOVE 0 TO PS-STARTED
               PERFORM VARYING PS-S2 FROM 1 BY 1 UNTIL PS-S2 > 20
                   IF PS-STARTED = 0 AND PS-BUF(PS-S2:1) NOT = "0"
                       MOVE PS-S2 TO PS-FROM
                       MOVE 1 TO PS-STARTED
                   END-IF
               END-PERFORM
               DISPLAY PS-BUF(PS-FROM:21 - PS-FROM) WITH NO ADVANCING
           END-IF.
           DISPLAY PS-LF WITH NO ADVANCING.
           STOP RUN.
       END FUNCTION ISY-END.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-FAIL.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-END.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-XS PIC X(16) VALUE "ERROR".
       01 PS-XD PIC 9.
       LINKAGE SECTION.
       01 LS-STEPS PIC S9(18).
       01 LS-CODE PIC X(24).
       01 PS-RET PIC 9.
       PROCEDURE DIVISION USING LS-STEPS LS-CODE RETURNING PS-RET.
           MOVE ISY-END(LS-STEPS, PS-XS, LS-CODE) TO PS-XD.
           MOVE 0 TO PS-RET.
           GOBACK.
       END FUNCTION ISY-FAIL.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-FIT.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-FAIL.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-T PIC S9(38).
       01 PS-Q PIC S9(38).
       01 PS-M PIC S9(38).
       01 PS-XS PIC X(16) VALUE "ERROR".
       01 PS-XC PIC X(24) VALUE "OVERFLOW".
       LINKAGE SECTION.
       01 LS-V PIC S9(38).
       01 LS-LO PIC S9(38).
       01 LS-HI PIC S9(38).
       01 LS-W PIC S9(38).
       01 LS-MODE PIC 9.
       01 LS-STEPS PIC S9(18).
       01 PS-RET PIC S9(38).
       PROCEDURE DIVISION USING LS-V LS-LO LS-HI LS-W LS-MODE LS-STEPS
           RETURNING PS-RET.
           IF LS-V >= LS-LO AND LS-V <= LS-HI
               MOVE LS-V TO PS-RET
               GOBACK
           END-IF.
           IF LS-MODE = 0
               MOVE ISY-FAIL(LS-STEPS, PS-XC) TO PS-RET
               MOVE 0 TO PS-RET
               GOBACK
           END-IF.
           IF LS-MODE = 2
               IF LS-V > LS-HI
                   MOVE LS-HI TO PS-RET
               ELSE
                   MOVE LS-LO TO PS-RET
               END-IF
               GOBACK
           END-IF.
           COMPUTE PS-T = LS-V - LS-LO.
           DIVIDE PS-T BY LS-W GIVING PS-Q REMAINDER PS-M.
           IF PS-M < 0
               COMPUTE PS-M = PS-M + LS-W
           END-IF.
           COMPUTE PS-RET = PS-M + LS-LO.
           GOBACK.
       END FUNCTION ISY-FIT.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-DECFIT.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-FAIL.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-XS PIC X(16) VALUE "ERROR".
       01 PS-XC PIC X(24) VALUE "OVERFLOW".
       LINKAGE SECTION.
       01 LS-M PIC S9(38).
       01 LS-MAX PIC S9(38).
       01 LS-STEPS PIC S9(18).
       01 PS-RET PIC S9(38).
       PROCEDURE DIVISION USING LS-M LS-MAX LS-STEPS RETURNING PS-RET.
           IF LS-M > LS-MAX OR LS-M < 0 - LS-MAX
               MOVE ISY-FAIL(LS-STEPS, PS-XC) TO PS-RET
           END-IF.
           MOVE LS-M TO PS-RET.
           GOBACK.
       END FUNCTION ISY-DECFIT.



       IDENTIFICATION DIVISION.
       FUNCTION-ID. ISY-RDIV.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       REPOSITORY.
           FUNCTION ISY-FAIL.
       DATA DIVISION.
       LOCAL-STORAGE SECTION.
       01 PS-Q PIC S9(38).
       01 PS-R1 PIC S9(38).
       01 PS-AR PIC S9(38).
       01 PS-AD PIC S9(38).
       01 PS-SIGN PIC S9(4).
       01 PS-2 PIC S9(38).
       01 PS-PAR PIC S9(38).
       01 PS-Q2 PIC S9(38).
       01 PS-XS PIC X(16) VALUE "ERROR".
       01 PS-XC PIC X(24) VALUE "INEXACT".
       LINKAGE SECTION.
       01 LS-NUM PIC S9(38).
       01 LS-DEN PIC S9(38).
       01 LS-MODE PIC 9.
       01 LS-STEPS PIC S9(18).
       01 PS-RET PIC S9(38).
       PROCEDURE DIVISION USING LS-NUM LS-DEN LS-MODE LS-STEPS RETURNING PS-RET.
           DIVIDE LS-NUM BY LS-DEN GIVING PS-Q REMAINDER PS-R1.
           IF PS-R1 = 0
               MOVE PS-Q TO PS-RET
               GOBACK
           END-IF.
           IF LS-MODE = 3
               MOVE ISY-FAIL(LS-STEPS, PS-XC) TO PS-RET
           END-IF.
           IF LS-MODE = 2
               MOVE PS-Q TO PS-RET
               GOBACK
           END-IF.
           MOVE FUNCTION ABS(PS-R1) TO PS-AR.
           MOVE FUNCTION ABS(LS-DEN) TO PS-AD.
           MOVE -1 TO PS-SIGN.
           IF LS-NUM < 0 AND LS-DEN < 0
               MOVE 1 TO PS-SIGN
           END-IF.
           IF LS-NUM > 0 AND LS-DEN > 0
               MOVE 1 TO PS-SIGN
           END-IF.
           COMPUTE PS-2 = PS-AR * 2.
           IF PS-2 > PS-AD
               COMPUTE PS-RET = PS-Q + PS-SIGN
               GOBACK
           END-IF.
           IF PS-2 < PS-AD
               MOVE PS-Q TO PS-RET
               GOBACK
           END-IF.
           IF LS-MODE = 1
               COMPUTE PS-RET = PS-Q + PS-SIGN
               GOBACK
           END-IF.
           ISY_TIE_COBOL
           GOBACK.
       END FUNCTION ISY-RDIV.


"""

# Empate exacto de half_even (el sabotaje half_even_as_half_up lo reemplaza).
TIE_CODE = {
    None: "           DIVIDE PS-Q BY 2 GIVING PS-Q2 REMAINDER PS-PAR\n"
          "           IF PS-PAR = 0\n"
          "               MOVE PS-Q TO PS-RET\n"
          "           ELSE\n"
          "               COMPUTE PS-RET = PS-Q + PS-SIGN\n"
          "           END-IF.",
    "half_even_as_half_up": "           COMPUTE PS-RET = PS-Q + PS-SIGN.",
}


def cob_ident(name: str) -> str:
    """Nombre de módulo COBOL a partir del nombre IR (prefijo de ruta incluido)."""
    return "ISY-" + name.upper().replace(".", "-")



COUNTERS = ("STEPS", "MAXSTEPS", "DEPTH", "MAXDEPTH", "EMITS", "MAXEMITS")

# Etiqueta de párrafo: nombre COBOL solo, cerrado con punto.
LABEL = re.compile(r"[A-Z][A-Z0-9-]*\.")


class Unit:
    """Una unidad COBOL: FUNCTION-ID (función IR) o PROGRAM-ID (main).

    `prefix` es el prefijo de los contadores (LS- en enlace, WS- en el
    programa principal); todo lo demás se declara en LOCAL/WORKING-STORAGE."""

    def __init__(self, ident: str, prefix: str, is_main: bool, repo: list | None):
        self.ident = ident
        self.prefix = prefix
        self.is_main = is_main
        self.repo = repo or []
        self.decls: list[str] = []
        self.lines: list[str] = []
        self.params: list[tuple[str, str]] = []      # (nombre, declaración)
        self.ret_item = ""
        self.indent = 7
        self._seen: set[str] = set()

    def decl(self, line: str) -> None:
        if line not in self._seen:
            self._seen.add(line)
            self.decls.append(line)

    def put(self, line: str) -> None:
        s = line.strip()
        # Un punto cierra TODOS los ámbitos abiertos (IF/ELSE/PEFORM): por eso
        # las sentencias no llevan punto salvo al cerrar una frase, y la frase
        # solo se cierra ante una etiqueta de párrafo o al final de la unidad.
        if LABEL.fullmatch(s):
            self.end_sentence()
        self.lines.append(" " * self.indent + line)

    def end_sentence(self) -> None:
        for i in range(len(self.lines) - 1, -1, -1):
            s = self.lines[i].strip()
            if not s or s.startswith("*>"):
                continue
            if not s.endswith("."):
                self.lines[i] += "."
            return

    def open(self, width: int = 4) -> None:
        self.indent += width

    def close(self, width: int = 4) -> None:
        self.indent -= width

    def body(self) -> str:
        return "\n".join(self.lines)

    def repo_lines(self) -> list[str]:
        """REPOSITORY: entradas separadas por COMA; el punto cierra la cláusula."""
        if not self.repo:
            return []
        names = sorted(self.repo)
        out = ["       ENVIRONMENT DIVISION.",
               "       CONFIGURATION SECTION.",
               "       REPOSITORY."]
        for k, name in enumerate(names):
            sep = "," if k < len(names) - 1 else "."
            out.append(f"           FUNCTION {name}{sep}")
        return out

    def text(self) -> str:
        out = ["       IDENTIFICATION DIVISION."]
        if self.is_main:
            out.append(f"       PROGRAM-ID. {self.ident}.")
        else:
            # Subprograma recursivo: GnuCOBOL 3.1 no propaga el retorno de una
            # FUNCTION-ID recursiva (sonda: el valor llega 0), y sin RECURSIVE
            # el LOCAL-STORAGE es estático y se pisan los marcos.
            out.append(f"       PROGRAM-ID. {self.ident} IS RECURSIVE.")
        out += self.repo_lines()
        if self.is_main:
            out += ["       DATA DIVISION.", "       WORKING-STORAGE SECTION."]
        else:
            out += ["       DATA DIVISION.", "       LOCAL-STORAGE SECTION."]
        out += self.decls
        if self.params:
            out.append("       LINKAGE SECTION.")
            out += [line for _, d in self.params for line in d.split("\n")]
        if self.is_main:
            out.append("       PROCEDURE DIVISION.")
        else:
            using = " ".join(name for name, _ in self.params)
            out.append(f"       PROCEDURE DIVISION USING {using}.")
        # La última sentencia del cuerpo debe cerrar con punto: END PROGRAM /
        # END FUNCTION no continúa la oración.
        self.end_sentence()
        out += self.lines
        out.append(f"       END PROGRAM {self.ident}.")
        return "\n".join(out) + "\n"


class CobolEmitter:
    """Traduce ISY-IR validada a un fuente GnuCOBOL por módulo."""

    def __init__(self, module: dict, sabotage: str | None = None):
        if sabotage not in TIE_CODE and sabotage not in ("div_floor",):
            raise ValueError(sabotage)
        self.module = module
        self.sabotage = sabotage
        self.fns = {f["name"]: f for f in module["functions"]}
        self.consts: dict[str, tuple[str, str]] = {}    # clave -> (nombre, decl)
        self.units: list[Unit] = []
        self.unit: Unit | None = None
        self.types: list = []
        self.tmp_n = 0
        self.loop_n = 0

    HELPERS = ("ISY-PUT-INT", "ISY-PUT-DEC", "ISY-PUT-BOOL", "ISY-EMIT-INT",
               "ISY-EMIT-DEC", "ISY-EMIT-BOOL", "ISY-TICK", "ISY-ENTER",
               "ISY-LEAVE", "ISY-END", "ISY-FAIL", "ISY-FIT", "ISY-DECFIT",
               "ISY-RDIV")

    # --- constantes: nunca se pasan literales por referencia -------------------
    def const(self, kind: str, t) -> str:
        key = f"{kind}:{t!r}"
        if key not in self.consts:
            if kind == "lo":
                value, pic = str(t.lo), "S9(38)"
            elif kind == "hi":
                value, pic = str(t.hi), "S9(38)"
            elif kind == "w":
                value, pic = str(1 << t.bits), "S9(38)"
            elif kind == "ovf":
                value, pic = str(OVF_CODE[t.ovf]), "9"
            elif kind == "max":
                value, pic = str(t.max_m), "S9(38)"
            elif kind == "nmax":
                value, pic = str(-t.max_m), "S9(38)"
            elif kind == "pow10":
                value, pic = str(10 ** t.s), "S9(38)"
            elif kind == "rnd":
                value, pic = str({"half_even": 0, "half_up": 1, "down": 2,
                                  "exact": 3}[t.rnd]), "9"
            elif kind == "scale":
                value, pic = str(t.s), "9(2)"
            elif kind == "pow32":
                value, pic = str(2 ** 32), "S9(38)"
            elif kind == "u64max":
                value, pic = str(2 ** 64 - 1), "S9(38)"
            else:
                raise AssertionError(kind)
            name = f"WS-C{len(self.consts)}-{kind}"
            self.consts[key] = (name, f"       01 {name} PIC {pic} VALUE {value}.")
        return self.consts[key][0]

    # --- PICs -------------------------------------------------------------------
    @staticmethod
    def pic(t) -> str:
        if isinstance(t, ArrT):
            return CobolEmitter.pic(t.elem)
        if isinstance(t, BoolT):
            return "9"
        if isinstance(t, IntT):
            return "S9(19)" if t.signed else "9(20)"
        if isinstance(t, DecT):
            return "S9(20)"
        raise AssertionError(f"fuera del alcance numérico de COBOL: {t}")

    @staticmethod
    def wide_pic(t) -> str:
        if isinstance(t, ArrT):
            return CobolEmitter.wide_pic(t.elem)
        if isinstance(t, BoolT):
            return "9"
        if isinstance(t, (IntT, DecT)):
            return "S9(38)"
        raise AssertionError(f"fuera del alcance numérico de COBOL: {t}")

    def temp(self, t, wide: bool = False) -> str:
        self.tmp_n += 1
        name = f"T{self.tmp_n:02d}"
        pic = self.wide_pic(t) if wide else self.pic(t)
        self.unit.decl(f"       01 {name} PIC {pic}.")
        return name

    def emit_item(self) -> str:
        """PIC S9(20) para el valor de un emit/R: coincide con el LINKAGE de
        ISY-EMIT-* (magnitud de 64 bits, signo aparte)."""
        self.tmp_n += 1
        name = f"E{self.tmp_n:02d}"
        self.unit.decl(f"       01 {name} PIC S9(20).")
        return name

    def item(self, t, wide: bool = False, occurs: int | None = None) -> str:
        self.tmp_n += 1
        name = f"T{self.tmp_n:02d}"
        if occurs is not None or isinstance(t, ArrT):
            elem_t = t.elem if isinstance(t, ArrT) else t
            n = occurs if occurs is not None else t.n
            pic = self.wide_pic(elem_t) if wide else self.pic(elem_t)
            self.unit.decl(f"       01 {name}.")
            self.unit.decl(f"       05 {name}-E OCCURS {n} PIC {pic}.")
        else:
            pic = self.wide_pic(t) if wide else self.pic(t)
            self.unit.decl(f"       01 {name} PIC {pic}.")
        return name

    @staticmethod
    def elem(name: str, k) -> str:
        return f"{name}-E({k})"

    def array_decl(self, name: str, t) -> None:
        """Arreglo como grupo + OCCURS: un ítem OCCURS suelto no puede pasarse
        por referencia (GnuCOBOL exige subíndice); el grupo sí."""
        self.unit.decl(f"       01 {name}.")
        self.unit.decl(f"       05 {name}-E OCCURS {t.n} PIC {self.pic(t.elem)}.")

    # --- nombres ----------------------------------------------------------------
    @property
    def c(self) -> str:
        return f"{self.unit.prefix}"

    def call_helpers(self) -> list[str]:
        return [f"{self.c}{n}" for n in COUNTERS]

    def fail(self, code: str) -> None:
        self.unit.put(f'MOVE "{code}" TO {self.c}ECODE')
        self.unit.put(f"MOVE ISY-FAIL({self.c}STEPS, {self.c}ECODE) TO {self.c}RET")

    def put_call(self, fn: str, args: list) -> None:
        self.unit.put(f"MOVE {fn}({', '.join(args)}) TO {self.c}RET")

    def call_fn(self, fn: str, args: list, result: str) -> None:
        """Invocación de una función IR: subprograma recursivo por CALL, con el
        resultado como último argumento por referencia."""
        self.unit.put(f'CALL "{fn}" USING '
                      f"{' '.join(args + self.call_helpers() + [result])}")

    def move(self, dst: str, src: str, t) -> None:
        """Asignación por valor: COBOL no copia tablas completas sin
        CORRESPONDING, así que los arreglos se copian hoja a hoja."""
        if isinstance(t, ArrT):
            for k in range(t.n):
                self.move(self.elem(dst, k + 1), self.elem(src, k + 1), t.elem)
        else:
            self.unit.put(f"MOVE {src} TO {dst}")

    def tick(self, enter: bool = False) -> None:
        if enter:
            self.put_call("ISY-ENTER", [f"{self.c}STEPS", f"{self.c}MAXSTEPS",
                                        f"{self.c}DEPTH", f"{self.c}MAXDEPTH"])
        else:
            self.put_call("ISY-TICK", [f"{self.c}STEPS", f"{self.c}MAXSTEPS"])

    # --- montaje -----------------------------------------------------------------
    def emit(self) -> str:
        for fn in self.module["functions"]:
            if fn["name"] != "main":
                self.fn_unit(fn)
        main_unit = self.main_unit(self.fns["main"])
        # Las constantes usadas en cualquier unidad se declaran en todas:
        # se recogen DESPUÉS de emitir todos los cuerpos, y el texto de cada
        # unidad se arma al final.
        for u in self.units:
            for _, decl in self.consts.values():
                u.decl(decl)
        main_text = main_unit.text()
        parts = [f"      *> generado por isyco.backends.cobol desde ISY-IR "
                 f"{self.module['source_sha256']}",
                 "      *> ola 2 (F5): núcleo numérico v0.1; str y struct NO "
                 "implementados (UNSUPPORTED).",
                 RUNTIME.replace("ISY_TIE_COBOL",
                                 TIE_CODE.get(self.sabotage, TIE_CODE[None])),
                 main_text,
                 *[u.text() for u in self.units if not u.is_main]]
        return "\n\n".join(parts)

    def counters_decl(self, unit: Unit) -> None:
        for n in COUNTERS:
            unit.decl(f"       01 {unit.prefix}{n} PIC S9(18) VALUE 0.")
        self.scratch_decl(unit)

    def scratch_decl(self, unit: Unit) -> None:
        unit.decl(f"       01 {unit.prefix}ECODE PIC X(24) VALUE SPACES.")
        unit.decl(f"       01 {unit.prefix}XS PIC X(16) VALUE SPACES.")
        unit.decl(f"       01 {unit.prefix}XC PIC X(24) VALUE SPACES.")

    def counters_linkage(self, unit: Unit) -> None:
        """Contadores compartidos: cada llamada los pasa por referencia (C usa
        globales; aquí basta con el mismo almacenamiento del llamador)."""
        for n in COUNTERS:
            unit.params.append((f"{unit.prefix}{n}",
                                f"01 {unit.prefix}{n} PIC S9(18)."))

    # --- unidades -----------------------------------------------------------------
    def fn_unit(self, fn: dict) -> None:
        ident = cob_ident(fn["name"])
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        unit = Unit(ident, "LS-", False, list(self.HELPERS))
        # El resultado viaja como último argumento por referencia: las
        # FUNCTION-ID recursivas de GnuCOBOL 3.1 no devuelven su valor. El hueco
        # existe aunque la función no retorne nada: el proemio y el epílogo escriben
        # su conteo de profundidad en `{prefijo}RET`, y el llamador en posición de
        # sentencia pasa un destino igualmente (CORE v0.1, `fn f() { }` + `f();`).
        unit.ret_item = f"{unit.prefix}RET"
        for p in fn["params"]:
            t = types[p]
            if isinstance(t, IntT):
                decl = f"01 LS-P{p} PIC {self.pic(t)}."
            elif isinstance(t, DecT):
                decl = f"01 LS-P{p} PIC {self.pic(t)}."
            elif isinstance(t, BoolT):
                decl = f"01 LS-P{p} PIC {self.pic(t)}."
            elif isinstance(t, ArrT):
                if not isinstance(t.elem, (IntT, DecT, BoolT)):
                    raise ValueError("arreglos de agredados: fuera de alcance COBOL")
                decl = (f"01 LS-P{p}.\n"
                        f"05 LS-P{p}-E OCCURS {t.n} PIC {self.pic(t.elem)}.")
            else:
                raise ValueError(f"parámetro fuera del alcance numérico: {t}")
            unit.params.append((f"LS-P{p}", decl))
        # Los contadores llegan por LINKAGE (el llamador ya los pasa en toda
        # llamada): así pasos y profundidad son globales, como en C.
        self.counters_linkage(unit)
        if ret is not None:
            unit.params.append((unit.ret_item,
                                f"01 {unit.ret_item} PIC {self.pic(ret)}."))
        else:
            unit.params.append((unit.ret_item, f"01 {unit.ret_item} PIC 9."))
        self.units.append(unit)
        self.unit = unit
        self.types = types
        self.tmp_n = 0
        self.scratch_decl(unit)
        # parámetros por valor: se copian a locales del marco (CORE §3.2)
        for p in fn["params"]:
            t = types[p]
            if isinstance(t, ArrT):
                self.array_decl(f"L{p}", t)
            else:
                unit.decl(f"       01 L{p} PIC {self.pic(t)}.")
            self.move(f"L{p}", f"LS-P{p}", t)
        # Locales que no son parámetros también viven en LOCAL-STORAGE.
        for idx, t in enumerate(types):
            if idx in fn["params"]:
                continue
            if isinstance(t, ArrT):
                self.array_decl(f"L{idx}", t)
            else:
                unit.decl(f"       01 L{idx} PIC {self.pic(t)}.")
        self.tick(enter=True)
        self.block(fn["body"])
        if ret is None:
            self.put_call("ISY-LEAVE", [f"{unit.prefix}DEPTH"])
            unit.put("GOBACK")
        else:
            # Inalcanzable: el validador exige `return` en todo camino (C
            # emite abort(); COBOL, un GOBACK tras decrementar la profundidad).
            self.put_call("ISY-LEAVE", [f"{unit.prefix}DEPTH"])
            unit.put("GOBACK")

    def main_unit(self, main: dict) -> str:
        ident = cob_ident("main")
        types = [ty_from_json(loc["ty"]) for loc in main["locals"]]
        ret = ty_from_json(main["ret"])
        repo = list(self.HELPERS)
        unit = Unit(ident, "WS-", True, repo)
        self.units.append(unit)
        self.unit = unit
        self.types = types
        self.tmp_n = 0
        self.counters_decl(unit)
        unit.decl("       01 WS-RET PIC 9 VALUE 0.")
        for name, pic, value in (
                ("WS-HEX", "X(65536)", "SPACES"),
                ("WS-C1", "X", "SPACES"), ("WS-C2", "X", "SPACES"),
                ("WS-BY", "9(3)", "0"), ("WS-NBYTE1", "9(3)", "0"),
                ("WS-PFX-E", "X(2)", '"E "'), ("WS-PFX-R", "X(2)", '"R "'),
                ("WS-ARGNO", "9(2)", "0"), ("WS-NBYTES", "9(4)", "1"),
                ("WS-N1", "9(3)", "0"), ("WS-N2", "9(3)", "0"),
                ("WS-HP", "9(5)", "1")):
            unit.decl(f"       01 {name} PIC {pic} VALUE {value}.")
        unit.decl("       01 WS-ARGN PIC X(64) VALUE SPACES.")
        # parámetros de main: un texto decodificado por hoja + el local tipado
        slots: list[tuple[object, str, int]] = []
        for p in main["params"]:
            t = types[p]
            if isinstance(t, ArrT):
                self.array_decl(f"L{p}", t)
                for k in range(t.n):
                    slots.append((t.elem, f"L{p}", k))
            elif isinstance(t, (IntT, DecT, BoolT)):
                unit.decl(f"       01 L{p} PIC {self.pic(t)}.")
                slots.append((t, "", p))
            else:
                raise ValueError(f"parámetro fuera del alcance numérico: {t}")
        # Tres primeros argumentos (límites) + un texto por hoja de parámetro.
        unit.decl(f"       01 WS-ARGS. 05 WS-ARG PIC X(64) "
                  f"OCCURS {3 + len(slots)} TIMES.")
        if ret is not None:
            unit.decl(f"       01 WS-MAINRET PIC {self.pic(ret)}.")
        for idx, t in enumerate(types):
            if idx in main["params"]:
                continue
            if isinstance(t, ArrT):
                self.array_decl(f"L{idx}", t)
            else:
                unit.decl(f"       01 L{idx} PIC {self.pic(t)}.")
        # --- cuerpo: decodificar el flujo hexadecimal y reconstruir la entrada
        # La envoltura pasa cada argumento en hexadecimal y X"01" entre ellos,
        # con X"FF" al final. ORD/CHAR de GnuCOBOL son 1-based: el dígito vale
        # ORD(c) - 49 y el byte b se escribe CHAR(b + 1).
        unit.put("MAIN-BEGIN.")
        unit.put("ACCEPT WS-HEX FROM STDIN")
        unit.put("WS-DECODE-TOP.")
        unit.open()
        unit.put("IF WS-HP > 65536")
        unit.open()
        unit.put("GO TO WS-DECODE-OUT")
        unit.close()
        unit.put("END-IF")
        unit.put('MOVE WS-HEX(WS-HP:1) TO WS-C1')
        unit.put("MOVE WS-HEX(WS-HP + 1:1) TO WS-C2")
        unit.put("COMPUTE WS-N1 = FUNCTION ORD(WS-C1) - 49")
        unit.put("IF WS-N1 > 9")
        unit.open()
        unit.put("COMPUTE WS-N1 = WS-N1 - 39")
        unit.close()
        unit.put("END-IF")
        unit.put("COMPUTE WS-N2 = FUNCTION ORD(WS-C2) - 49")
        unit.put("IF WS-N2 > 9")
        unit.open()
        unit.put("COMPUTE WS-N2 = WS-N2 - 39")
        unit.close()
        unit.put("END-IF")
        unit.put("COMPUTE WS-BY = WS-N1 * 16 + WS-N2")
        unit.put("IF WS-BY = 255")
        unit.open()
        unit.put("GO TO WS-DECODE-OUT")
        unit.close()
        unit.put("END-IF")
        unit.put("IF WS-BY = 1")
        unit.open()
        unit.put("MOVE WS-ARGN TO WS-ARG(WS-ARGNO + 1)")
        unit.put("ADD 1 TO WS-ARGNO")
        unit.put("MOVE SPACES TO WS-ARGN")
        unit.put("MOVE 1 TO WS-NBYTES")
        unit.close()
        unit.put("ELSE")
        unit.open()
        unit.put("COMPUTE WS-NBYTE1 = WS-BY + 1")
        unit.put("MOVE FUNCTION CHAR(WS-NBYTE1) TO WS-C1")
        unit.put("STRING WS-C1 DELIMITED SIZE INTO WS-ARGN")
        unit.put("    WITH POINTER WS-NBYTES")
        unit.put("END-STRING")
        unit.close()
        unit.put("END-IF")
        unit.put("ADD 2 TO WS-HP")
        unit.put("GO TO WS-DECODE-TOP")
        unit.close()
        unit.put("WS-DECODE-OUT.")
        unit.put("MAIN-DECODED.")
        for k, limit in enumerate(("MAXSTEPS", "MAXDEPTH", "MAXEMITS")):
            unit.put(f"MOVE FUNCTION NUMVAL(FUNCTION TRIM(WS-ARG({k + 1}))) "
                     f"TO WS-{limit}")
        # Cada argumento quedó en su propia hoja; ahora al local tipado.
        # Los decimales viajan ya escalados (m = valor * 10^s, como en C).
        for k, (t, table, idx) in enumerate(slots):
            target = f"L{idx}" if table == "" else self.elem(table, idx + 1)
            name = f"WS-ARG({4 + k})"
            if isinstance(t, BoolT):
                unit.put(f"IF FUNCTION TRIM({name}) = \"1\" THEN")
                unit.open()
                unit.put(f"MOVE 1 TO {target}")
                unit.close()
                unit.put("ELSE")
                unit.open()
                unit.put(f"MOVE 0 TO {target}")
                unit.close()
                unit.put("END-IF")
            else:
                unit.put(f"MOVE FUNCTION NUMVAL(FUNCTION TRIM({name})) "
                         f"TO {target}")
        self.tick(enter=True)
        self.block(main["body"])
        unit.put("MAIN-DONE.")
        if ret is not None:
            self.emit_return_line(ret, "WS-MAINRET")
        unit.put('MOVE "HALTED" TO WS-XS')
        unit.put("MOVE SPACES TO WS-XC")
        unit.put("MOVE ISY-END(WS-STEPS, WS-XS, WS-XC) TO WS-RET")
        # El texto de main se arma al final de emit(), cuando ya se conocen
        # todas las constantes usadas.
        return unit

    def emit_return_line(self, ret, source: str) -> None:
        """Línea R: mismo formato canónico que un emit, sin contar emits."""
        unit = self.unit
        unit.decl("       01 WS-RETVAL PIC S9(20).")
        if isinstance(ret, BoolT):
            unit.put(f"IF {source} = 1 THEN")
            unit.open()
            unit.put('DISPLAY "R true" WITH NO ADVANCING')
            unit.close()
            unit.put("ELSE")
            unit.open()
            unit.put('DISPLAY "R false" WITH NO ADVANCING')
            unit.close()
            unit.put("END-IF")
            unit.put('MOVE X"0A" TO WS-C2')
            unit.put("DISPLAY WS-C2 WITH NO ADVANCING")
            return
        if isinstance(ret, IntT):
            unit.put(f"MOVE {source} TO WS-RETVAL")
            unit.put("MOVE ISY-PUT-INT(WS-PFX-R, WS-RETVAL) TO WS-RET")
            return
        unit.put(f"MOVE {source} TO WS-RETVAL")
        unit.put(f"MOVE ISY-PUT-DEC(WS-PFX-R, WS-RETVAL, "
                 f"{self.const('scale', ret)}) TO WS-RET")

    # --- sentencias -----------------------------------------------------------------
    def block(self, stmts: list) -> None:
        for s in stmts:
            self.stmt(s)

    def stmt(self, s: dict) -> None:
        kind = s["s"]
        unit = self.unit
        unit.put(f"      *> {kind} {s['at']}")
        self.tick()
        if kind in ("let", "set"):
            value = self.expr(s["value"])
            self.move(f"L{s['local']}", value, self.types[s["local"]])
        elif kind == "set_index":
            index = self.expr(s["index"])
            value = self.expr(s["value"])
            arr_t = self.types[s["local"]]
            unit.put(f"IF {index} < 0 OR {index} >= {arr_t.n} THEN")
            unit.open()
            self.fail("INDEX_OUT_OF_BOUNDS")
            unit.close()
            unit.put("END-IF")
            local = f"L{s['local']}"
            unit.put(f"MOVE {value} TO {self.elem(local, f'{index} + 1')}")
        elif kind == "set_path":
            raise ValueError("set_path (structs) fuera del alcance de COBOL")
        elif kind == "if":
            cond = self.expr(s["cond"])
            unit.put(f"IF {cond} = 1 THEN")
            unit.open()
            self.block(s["then"])
            unit.close()
            if s["else"] is not None:
                unit.put("ELSE")
                unit.open()
                self.block(s["else"])
                unit.close()
            unit.put("END-IF")
        elif kind == "while":
            self.while_loop(s)
        elif kind == "break":
            unit.put("EXIT PERFORM")
        elif kind == "continue":
            unit.put("EXIT PERFORM CYCLE")
        elif kind == "return":
            target = None
            if s["value"] is not None:
                value = self.expr(s["value"])
                target = self.item(ty_from_json(s["value"]["ty"]))
                unit.put(f"MOVE {value} TO {target}")
            self.put_call("ISY-LEAVE", [f"{self.c}DEPTH"])
            if self.unit.is_main:
                if target is not None:
                    unit.put(f"MOVE {target} TO WS-MAINRET")
                unit.put("GO TO MAIN-DONE")
            else:
                if target is not None:
                    unit.put(f"MOVE {target} TO {self.unit.ret_item}")
                unit.put("GOBACK")
        elif kind == "emit":
            value = self.expr(s["value"])
            t = ty_from_json(s["value"]["ty"])
            if isinstance(t, BoolT):
                self.put_call("ISY-EMIT-BOOL",
                              [f"{self.c}EMITS", f"{self.c}MAXEMITS",
                               f"{self.c}STEPS", value])
            elif isinstance(t, IntT):
                val = self.emit_item()
                unit.put(f"MOVE {value} TO {val}")
                self.put_call("ISY-EMIT-INT",
                              [f"{self.c}EMITS", f"{self.c}MAXEMITS",
                               f"{self.c}STEPS", val])
            else:
                val = self.emit_item()
                unit.put(f"MOVE {value} TO {val}")
                self.put_call("ISY-EMIT-DEC",
                              [f"{self.c}EMITS", f"{self.c}MAXEMITS",
                               f"{self.c}STEPS", val, self.const("scale", t)])
        elif kind == "call":
            args = self.expr_args(s["args"])
            ret = self.fns[s["fn"]]["ret"]
            result = self.item(ty_from_json(ret) if ret is not None else BoolT())
            self.call_fn(cob_ident(s["fn"]), args, result)
        else:
            raise AssertionError(kind)

    def while_loop(self, s: dict) -> None:
        """PERFORM en línea: un nombre de párrafo no puede ir dentro de un IF
        (GnuCOBOL lo rechaza), y EXIT PERFORM [CYCLE] es break/continue."""
        unit = self.unit
        self.loop_n += 1
        flag = f"{unit.prefix}LP{self.loop_n}-END"
        unit.decl(f"       01 {flag} PIC 9 VALUE 0.")
        unit.put(f"MOVE 0 TO {flag}")
        unit.put(f"PERFORM UNTIL {flag} = 1")
        unit.open()
        self.tick()
        cond = self.expr(s["cond"])
        unit.put(f"IF {cond} = 1 THEN")
        unit.open()
        self.block(s["body"])
        unit.close()
        unit.put("ELSE")
        unit.open()
        unit.put(f"MOVE 1 TO {flag}")
        unit.close()
        unit.put("END-IF")
        unit.close()
        unit.put("END-PERFORM")

    def expr_args(self, exprs: list) -> list[str]:
        return [self.expr(a) for a in exprs]

    # --- expresiones -----------------------------------------------------------------
    def expr(self, e: dict) -> str:
        kind = e["k"]
        t = ty_from_json(e["ty"])
        unit = self.unit
        if kind == "const":
            dst = self.item(t)
            value = parse_canonical(e["v"], t)
            if isinstance(t, BoolT):
                value = 1 if value else 0
            unit.put(f"MOVE {value} TO {dst}")
            return dst
        if kind == "local":
            return f"L{e['id']}"
        if kind == "call":
            args = self.expr_args(e["args"])
            fn_name = cob_ident(e["fn"])
            dst = self.item(t)
            self.call_fn(fn_name, args, dst)
            return dst
        if kind == "index":
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            arr_t = ty_from_json(e["base"]["ty"])
            unit.put(f"IF {index} < 0 OR {index} >= {arr_t.n} THEN")
            unit.open()
            self.fail("INDEX_OUT_OF_BOUNDS")
            unit.close()
            unit.put("END-IF")
            dst = self.item(t)
            unit.put(f"MOVE {self.elem(base, f'{index} + 1')} TO {dst}")
            return dst
        if kind == "not":
            src = self.expr(e["e"])
            dst = self.item(BoolT())
            unit.put(f"MOVE 0 TO {dst}")
            unit.put(f"IF {src} = 0 THEN")
            unit.open()
            unit.put(f"MOVE 1 TO {dst}")
            unit.close()
            unit.put("END-IF")
            return dst
        if kind == "neg":
            return self.neg(e, t)
        if kind in ("and", "or"):
            a = self.expr(e["a"])
            dst = self.item(BoolT())
            unit.put(f"MOVE {a} TO {dst}")
            test = "1" if kind == "and" else "0"
            unit.put(f"IF {dst} = {test} THEN")
            unit.open()
            b = self.expr(e["b"])
            unit.put(f"MOVE {b} TO {dst}")
            unit.close()
            unit.put("END-IF")
            return dst
        if kind == "cmp":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            op = {"eq": "=", "ne": "NOT =", "lt": "<", "le": "NOT >",
                  "gt": ">", "ge": "NOT <"}[e["op"]]
            dst = self.item(BoolT())
            unit.put(f"MOVE 1 TO {dst}")
            unit.put(f"IF NOT ({a} {op} {b}) THEN")
            unit.open()
            unit.put(f"MOVE 0 TO {dst}")
            unit.close()
            unit.put("END-IF")
            return dst
        if kind == "bin":
            return self.binary(e, t)
        if kind == "array":
            dst = self.item(t, occurs=t.n)
            for k, item in enumerate(e["elems"]):
                v = self.expr(item)
                unit.put(f"MOVE {v} TO {self.elem(dst, k + 1)}")
            return dst
        if kind == "repeat":
            dst = self.item(t, occurs=t.n)
            v = self.expr(e["elem"])
            for k in range(t.n):
                unit.put(f"MOVE {v} TO {self.elem(dst, k + 1)}")
            return dst
        if kind == "cast":
            return self.cast(e, t)
        raise AssertionError(kind)

    def neg(self, e: dict, t) -> str:
        unit = self.unit
        src = self.expr(e["e"])
        wide = self.item(t, wide=True)
        unit.put(f"COMPUTE {wide} = 0 - {src}")
        dst = self.item(t)
        if isinstance(t, IntT):
            unit.put(f"MOVE ISY-FIT({wide}, {self.const('lo', t)}, "
                     f"{self.const('hi', t)}, {self.const('w', t)}, "
                     f"{self.const('ovf', t)}, {self.c}STEPS) TO {dst}")
        else:
            unit.put(f"MOVE ISY-DECFIT({wide}, {self.const('max', t)}, "
                     f"{self.c}STEPS) TO {dst}")
        return dst

    def binary(self, e: dict, t) -> str:
        unit = self.unit
        a = self.expr(e["a"])
        b = self.expr(e["b"])
        op = e["op"]
        if isinstance(t, IntT):
            if op in ("div", "rem"):
                unit.put(f"IF {b} = 0 THEN")
                unit.open()
                self.fail("DIV_ZERO")
                unit.close()
                unit.put("END-IF")
                quotient = self.item(t, wide=True)
                remainder = self.item(t, wide=True)
                unit.put(f"DIVIDE {a} BY {b} GIVING {quotient} "
                         f"REMAINDER {remainder}")
                if op == "div" and self.sabotage == "div_floor":
                    unit.put(f"IF {remainder} NOT = 0 AND "
                             f"(({a} < 0 AND {b} > 0) OR "
                             f"({a} > 0 AND {b} < 0)) THEN")
                    unit.open()
                    unit.put(f"COMPUTE {quotient} = {quotient} - 1")
                    unit.close()
                    unit.put("END-IF")
                dst = self.item(t)
                value = quotient if op == "div" else remainder
                unit.put(f"MOVE ISY-FIT({value}, {self.const('lo', t)}, "
                         f"{self.const('hi', t)}, {self.const('w', t)}, "
                         f"{self.const('ovf', t)}, {self.c}STEPS) TO {dst}")
                return dst
            wide = self.item(t, wide=True)
            if op == "mul":
                if t.bits == 64 and not t.signed:
                    return self.u64_mul(e, t, a, b)
                arith = "*"
            else:
                arith = {"add": "+", "sub": "-"}[op]
            unit.put(f"COMPUTE {wide} = {a} {arith} {b}")
            dst = self.item(t)
            unit.put(f"MOVE ISY-FIT({wide}, {self.const('lo', t)}, "
                     f"{self.const('hi', t)}, {self.const('w', t)}, "
                     f"{self.const('ovf', t)}, {self.c}STEPS) TO {dst}")
            return dst
        # decimales: m escalado, un solo redondeo (isy_rdiv)
        mx = self.const("max", t)
        if op in ("add", "sub"):
            wide = self.item(t, wide=True)
            arith = "+" if op == "add" else "-"
            unit.put(f"COMPUTE {wide} = {a} {arith} {b}")
            dst = self.item(t)
            unit.put(f"MOVE ISY-DECFIT({wide}, {mx}, {self.c}STEPS) TO {dst}")
            return dst
        if op == "mul":
            wide_a = self.item(t, wide=True)
            wide_b = self.item(t, wide=True)
            prod = self.item(t, wide=True)
            unit.put(f"MOVE {a} TO {wide_a}")
            unit.put(f"MOVE {b} TO {wide_b}")
            unit.put(f"COMPUTE {prod} = {wide_a} * {wide_b}")
            q = self.item(t, wide=True)
            unit.put(f"MOVE ISY-RDIV({prod}, {self.const('pow10', t)}, "
                     f"{self.const('rnd', t)}, {self.c}STEPS) TO {q}")
            dst = self.item(t)
            unit.put(f"MOVE ISY-DECFIT({q}, {mx}, {self.c}STEPS) TO {dst}")
            return dst
        unit.put(f"IF {b} = 0 THEN")
        unit.open()
        self.fail("DIV_ZERO")
        unit.close()
        unit.put("END-IF")
        num = self.item(t, wide=True)
        unit.put(f"COMPUTE {num} = {a} * {self.const('pow10', t)}")
        # LINKAGE se pasa por referencia: el divisor debe tener la misma
        # anchura (S9(38)) que declara ISY-RDIV, o lee memoria contigua.
        den = self.item(t, wide=True)
        unit.put(f"MOVE {b} TO {den}")
        q = self.item(t, wide=True)
        unit.put(f"MOVE ISY-RDIV({num}, {den}, {self.const('rnd', t)}, "
                 f"{self.c}STEPS) TO {q}")
        dst = self.item(t)
        unit.put(f"MOVE ISY-DECFIT({q}, {mx}, {self.c}STEPS) TO {dst}")
        return dst

    def u64_mul(self, e: dict, t, a: str, b: str) -> str:
        """u64*u64: 39 dígitos no caben en zoned COBOL; se opera con miembros
        de 32 bits (módulo 2^64) como manda la regla de overflow."""
        unit = self.unit
        ah, al = self.item(t, wide=True), self.item(t, wide=True)
        bh, bl = self.item(t, wide=True), self.item(t, wide=True)
        unit.put(f"DIVIDE {a} BY {self.const('pow32', t)} GIVING {ah} "
                 f"REMAINDER {al}")
        unit.put(f"DIVIDE {b} BY {self.const('pow32', t)} GIVING {bh} "
                 f"REMAINDER {bl}")
        p = self.item(t, wide=True)
        q = self.item(t, wide=True)
        r = self.item(t, wide=True)
        v1 = self.item(t, wide=True)
        unit.put(f"COMPUTE {p} = {al} * {bl}")
        unit.put(f"COMPUTE {q} = {ah} * {bl} + {al} * {bh}")
        unit.put(f"COMPUTE {r} = {ah} * {bh}")
        unit.put(f"COMPUTE {v1} = {q} * {self.const('pow32', t)} + {p}")
        dst = self.item(t)
        unit.put(f"IF {r} > 0 OR {v1} NOT < {self.const('u64max', t)} THEN")
        unit.open()
        dst2 = self.item(t, wide=True)
        unit.put(f"MOVE ISY-FIT({v1}, {self.const('lo', t)}, "
                 f"{self.const('u64max', t)}, "
                 f"{self.const('w', t)}, {self.const('ovf', t)}, "
                 f"{self.c}STEPS) TO {dst2}")
        unit.put(f"MOVE {dst2} TO {dst}")
        unit.close()
        unit.put("ELSE")
        unit.open()
        unit.put(f"MOVE {v1} TO {dst}")
        unit.close()
        unit.put("END-IF")
        return dst

    def cast(self, e: dict, dst) -> str:
        unit = self.unit
        src = ty_from_json(e["e"]["ty"])
        if isinstance(src, StrT) or isinstance(dst, StrT) or isinstance(src, StructT) \
                or isinstance(dst, StructT):
            raise ValueError("casts con str/struct: fuera del alcance de COBOL")
        x = self.expr(e["e"])
        if isinstance(src, IntT) and isinstance(dst, IntT):
            wide = self.item(dst, wide=True)
            unit.put(f"MOVE {x} TO {wide}")
            t = self.item(dst)
            unit.put(f"MOVE ISY-FIT({wide}, {self.const('lo', dst)}, "
                     f"{self.const('hi', dst)}, {self.const('w', dst)}, "
                     f"{self.const('ovf', dst)}, {self.c}STEPS) TO {t}")
            return t
        if isinstance(src, IntT):
            wide = self.item(dst, wide=True)
            unit.put(f"COMPUTE {wide} = {x} * {self.const('pow10', dst)}")
            t = self.item(dst)
            unit.put(f"MOVE ISY-DECFIT({wide}, {self.const('max', dst)}, "
                     f"{self.c}STEPS) TO {t}")
            return t
        if isinstance(dst, IntT):
            quotient = self.item(dst, wide=True)
            unit.put(f"DIVIDE {x} BY {self.const('pow10', src)} "
                     f"GIVING {quotient}")
            t = self.item(dst)
            unit.put(f"MOVE ISY-FIT({quotient}, {self.const('lo', dst)}, "
                     f"{self.const('hi', dst)}, {self.const('w', dst)}, "
                     f"{self.const('ovf', dst)}, {self.c}STEPS) TO {t}")
            return t
        wide = self.item(dst, wide=True)
        unit.put(f"COMPUTE {wide} = {x} * {self.const('pow10', dst)}")
        q = self.item(dst, wide=True)
        unit.put(f"MOVE ISY-RDIV({wide}, {self.const('pow10', src)}, "
                 f"{self.const('rnd', dst)}, {self.c}STEPS) TO {q}")
        t = self.item(dst)
        unit.put(f"MOVE ISY-DECFIT({q}, {self.const('max', dst)}, "
                 f"{self.c}STEPS) TO {t}")
        return t


def emit_cobol(module: dict, sabotage: str | None = None) -> str:
    return CobolEmitter(module, sabotage).emit()


# --- backend ISY_BACKEND/1 ------------------------------------------------------------

class CobolBackend(Backend):
    name = "cobol"
    extension = ".cob"
    features = FEATURES
    sabotages = ("half_even_as_half_up", "div_floor")

    def toolchain(self) -> str | None:
        cc = shutil.which("cobc")
        if not cc:
            return None
        first = subprocess.run([cc, "--version"], capture_output=True,
                               text=True).stdout.split("\n")[0]
        return f"cobc: {first}"

    def emit(self, module: dict, sabotage: str | None = None) -> str:
        return emit_cobol(module, sabotage)

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        # El binario final es un envoltorio bash: GnuCOBOL 3.1 no expone argv,
        # así que los argumentos se canalizan por stdin en hexadecimal.
        return ["bash", "-c", 'cobc -x -free -o "$1.prog" "$1" && '
                             'k=$(basename "$1.prog") && '
                             'cat > "$2" <<\'WRAP\' && chmod +x "$2" && '
                             'sed -i "s|PROGNAME|$k|" "$2"\n'
                             '#!/bin/bash\n'
                             'd="$(cd "$(dirname "$0")" && pwd)"\n'
                             '{ { for a in "$@"; do printf "%s" "$a"; '
                             'printf \'\\001\'; done; printf \'\\377\'; } | '
                             'od -An -v -tx1 | tr -d \' \\n\'; '
                             'printf \'\\n\'; } | '
                             '"$d/PROGNAME"\n'
                             'WRAP',
                "bash", str(source), str(binary)]


BACKEND = CobolBackend()


def run_cobol(data: bytes, inputs: list, limits: dict | None = None,
              trace: str = "none", timeout_ms: int | None = 60_000,
              sabotage: str | None = None, extra_flags: tuple = ()) -> tuple[dict, list]:
    """Mismo contrato que interp.run, ejecutando el binario GnuCOBOL."""
    return BACKEND.run(data, inputs, limits, trace, timeout_ms, sabotage, extra_flags)
