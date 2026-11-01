"""Lexer de v0.1 (spec §2), con strings y palabras nuevas de CORE v0.3."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import InvalidProgram
from .versions import has

KEYWORDS = {
    "isyco", "fn", "let", "if", "else", "while", "break", "continue", "return",
    "emit", "and", "or", "not", "true", "false", "as", "bool", "int", "dec",
    "signed", "unsigned", "trap", "wrap", "sat", "half_even", "half_up", "down",
    "exact", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64",
}

KEYWORDS_V03 = {"str", "struct", "len", "slice", "chr"}
KEYWORDS_V04 = {"import", "pub"}
#: CORE v0.5 V2: `for` se reserva; `in` NO (V3) — sigue siendo un IDENT contextual.
KEYWORDS_V05 = {"for"}
ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}

# Más largos primero para que "->" gane a "-".
OPERATORS = ["->", "==", "!=", "<=", ">=", "<", ">", "+", "-", "*", "/", "%",
             "(", ")", "{", "}", "[", "]", ",", ";", ":", "!", "=", "."]


@dataclass(frozen=True)
class Token:
    kind: str   # INT | DEC | STR | IDENT | KW | OP | EOF
    text: str   # en STR, el valor ya sin comillas ni escapes
    at: str     # "línea:columna"


def decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data:
        raise InvalidProgram("ENCODING", "1:1")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidProgram("ENCODING", None, str(exc)) from None


def header_version(source: str) -> str | None:
    """Versión de la cabecera, leída antes de tokenizar: las reglas léxicas de v0.3
    (strings y palabras nuevas) solo valen con `isyco 0.3`, así ningún programa
    v0.1/v0.2 cambia de significado."""
    words: list[str] = []
    i, n = 0, len(source)
    while i < n and len(words) < 2:
        if source[i] in " \t\n":
            i += 1
        elif source[i] == "#":
            while i < n and source[i] != "\n":
                i += 1
        else:
            j = i
            while j < n and source[j] not in " \t\n#":
                j += 1
            words.append(source[i:j])
            i = j
    return words[1] if len(words) == 2 and words[0] == "isyco" else None


def tokenize(source: str, prefix: str = "") -> list[Token]:
    """prefix: `ruta.isy:` para un módulo importado (CORE v0.4 P5)."""
    version = header_version(source)
    v03 = has(version, "v03")
    keywords = KEYWORDS | KEYWORDS_V03 if v03 else KEYWORDS
    if has(version, "v04"):
        keywords = keywords | KEYWORDS_V04
    if has(version, "v05"):
        keywords = keywords | KEYWORDS_V05
    tokens: list[Token] = []
    i, line, col = 0, 1, 1
    n = len(source)

    def advance(count: int) -> None:
        nonlocal i, line, col
        for _ in range(count):
            if source[i] == "\n":
                line, col = line + 1, 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = source[i]
        at = f"{prefix}{line}:{col}"
        if ch in " \t\n":
            advance(1)
        elif ch == "#":
            while i < n and source[i] != "\n":
                advance(1)
        elif ch == "@":
            raise InvalidProgram("RESERVED", at)
        elif ch.isascii() and ch.isdigit():
            j = i
            while j < n and (source[j].isdigit() or source[j] == "_") and source[j].isascii():
                j += 1
            if j < n and source[j] == "." and j + 1 < n and source[j + 1].isdigit():
                if "_" in source[i:j]:
                    raise InvalidProgram("SYNTAX", at, "'_' no se permite en literales decimales")
                k = j + 1
                while k < n and source[k].isascii() and source[k].isdigit():
                    k += 1
                tokens.append(Token("DEC", source[i:k], at))
                advance(k - i)
            else:
                text = source[i:j]
                if text.endswith("_"):
                    raise InvalidProgram("SYNTAX", at, "literal termina en '_'")
                tokens.append(Token("INT", text, at))
                advance(j - i)
        elif ch.isascii() and (ch.isalpha() or ch == "_"):
            j = i
            while j < n and source[j].isascii() and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            tokens.append(Token("KW" if word in keywords else "IDENT", word, at))
            advance(j - i)
        elif ch == '"' and v03:
            j, chars = i + 1, []
            while True:
                if j >= n or source[j] == "\n":
                    raise InvalidProgram("SYNTAX", at, "string sin cerrar")
                c = source[j]
                if c == '"':
                    break
                if c == "\\":
                    if j + 1 >= n or source[j + 1] not in ESCAPES:
                        raise InvalidProgram("SYNTAX", at, "escape desconocido")
                    chars.append(ESCAPES[source[j + 1]])
                    j += 2
                    continue
                if not (c == "\t" or " " <= c <= "~"):
                    raise InvalidProgram("ENCODING", at, f"byte no permitido en un string: {c!r}")
                chars.append(c)
                j += 1
            tokens.append(Token("STR", "".join(chars), at))
            advance(j + 1 - i)
        else:
            for op in OPERATORS:
                if source.startswith(op, i):
                    tokens.append(Token("OP", op, at))
                    advance(len(op))
                    break
            else:
                raise InvalidProgram("SYNTAX", at, f"carácter inesperado {ch!r}")
    tokens.append(Token("EOF", "", f"{prefix}{line}:{col}"))
    return tokens
