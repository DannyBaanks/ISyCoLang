"""Lexer de v0.1 (spec §2)."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import InvalidProgram

KEYWORDS = {
    "isyco", "fn", "let", "if", "else", "while", "break", "continue", "return",
    "emit", "and", "or", "not", "true", "false", "as", "bool", "int", "dec",
    "signed", "unsigned", "trap", "wrap", "sat", "half_even", "half_up", "down",
    "exact", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64",
}

# Más largos primero para que "->" gane a "-".
OPERATORS = ["->", "==", "!=", "<=", ">=", "<", ">", "+", "-", "*", "/", "%",
             "(", ")", "{", "}", "[", "]", ",", ";", ":", "!", "="]


@dataclass(frozen=True)
class Token:
    kind: str   # INT | DEC | IDENT | KW | OP | EOF
    text: str
    at: str     # "línea:columna"


def decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data:
        raise InvalidProgram("ENCODING", "1:1")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidProgram("ENCODING", None, str(exc)) from None


def tokenize(source: str) -> list[Token]:
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
        at = f"{line}:{col}"
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
            tokens.append(Token("KW" if word in KEYWORDS else "IDENT", word, at))
            advance(j - i)
        else:
            for op in OPERATORS:
                if source.startswith(op, i):
                    tokens.append(Token("OP", op, at))
                    advance(len(op))
                    break
            else:
                raise InvalidProgram("SYNTAX", at, f"carácter inesperado {ch!r}")
    tokens.append(Token("EOF", "", f"{line}:{col}"))
    return tokens
