"""Parser de descenso recursivo para la gramática de spec §2.1."""
from __future__ import annotations

from . import ast as A
from .errors import InvalidProgram
from .lexer import Token
from .types import INT_ALIASES, ArrT, BoolT, DecT, IntT

CMP_OPS = {"==", "!=", "<", "<=", ">", ">="}
ROUND_MODES = {"half_even", "half_up", "down", "exact"}
MAX_ARRAY = 65536
SUPPORTED_VERSIONS = {"0.1", "0.2"}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.version = "0.1"

    # --- utilidades -----------------------------------------------------------
    @property
    def tok(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def is_(self, text: str) -> bool:
        return self.tok.kind in ("OP", "KW") and self.tok.text == text

    def take(self) -> Token:
        token = self.tok
        self.pos += 1
        return token

    def expect(self, text: str) -> Token:
        if not self.is_(text):
            self.fail(f"se esperaba {text!r}")
        return self.take()

    def accept(self, text: str) -> bool:
        if self.is_(text):
            self.pos += 1
            return True
        return False

    def fail(self, detail: str):
        raise InvalidProgram("SYNTAX", self.tok.at, f"{detail}, llegó {self.tok.text!r}")

    def ident(self) -> Token:
        if self.tok.kind != "IDENT":
            self.fail("se esperaba un identificador")
        return self.take()

    def nat(self) -> int:
        if self.tok.kind != "INT":
            self.fail("se esperaba un número natural")
        return int(self.take().text.replace("_", ""))

    # --- archivo --------------------------------------------------------------
    def program(self) -> A.Program:
        if not (self.is_("isyco") and self.peek().kind == "DEC"
                and self.peek().text in SUPPORTED_VERSIONS):
            self.fail(f"la cabecera debe ser 'isyco' + una de {sorted(SUPPORTED_VERSIONS)}")
        self.version = self.peek().text
        self.pos += 2
        fns: dict[str, A.Fn] = {}
        while self.tok.kind != "EOF":
            fn = self.fn_decl()
            if fn.name in fns:
                raise InvalidProgram("DUPLICATE_NAME", fn.at, fn.name)
            fns[fn.name] = fn
        return A.Program(fns, self.version)

    def fn_decl(self) -> A.Fn:
        at = self.expect("fn").at
        name = self.ident().text
        self.expect("(")
        params = []
        if not self.is_(")"):
            while True:
                ptok = self.ident()
                self.expect(":")
                params.append((ptok.text, self.type_(), ptok.at))
                if not self.accept(","):
                    break
        self.expect(")")
        ret = self.type_() if self.accept("->") else None
        emits = False
        if self.accept("!"):
            self.expect("emit")
            emits = True
        return A.Fn(at, name, params, ret, emits, self.block())

    # --- tipos ----------------------------------------------------------------
    def type_(self):
        token = self.tok
        if self.accept("bool"):
            return BoolT()
        if token.kind == "KW" and token.text in INT_ALIASES:
            self.pos += 1
            return INT_ALIASES[token.text]
        if self.accept("int"):
            self.expect("<")
            bits_tok = self.take()
            if bits_tok.kind != "INT" or bits_tok.text not in ("8", "16", "32", "64"):
                raise InvalidProgram("SYNTAX", bits_tok.at, "BITS debe ser 8, 16, 32 o 64")
            self.expect(",")
            if not (self.is_("signed") or self.is_("unsigned")):
                self.fail("se esperaba signed o unsigned")
            signed = self.take().text == "signed"
            self.expect(",")
            if not any(self.is_(m) for m in ("trap", "wrap", "sat")):
                self.fail("se esperaba trap, wrap o sat")
            ovf = self.take().text
            self.expect(">")
            return IntT(int(bits_tok.text), signed, ovf)
        if self.accept("dec"):
            self.expect("<")
            p = self.nat()
            self.expect(",")
            s = self.nat()
            rnd = "half_even"
            if self.accept(","):
                if not (self.tok.kind == "KW" and self.tok.text in ROUND_MODES):
                    self.fail("se esperaba un modo de redondeo")
                rnd = self.take().text
            self.expect(">")
            if not (1 <= p <= 18 and 0 <= s <= p):
                raise InvalidProgram("DEC_PARAMS", token.at, f"dec<{p},{s}>")
            return DecT(p, s, rnd)
        if self.accept("["):
            elem = self.type_()
            if isinstance(elem, ArrT):
                raise InvalidProgram("SYNTAX", token.at, "los arreglos solo contienen escalares")
            self.expect(";")
            n = self.nat()
            self.expect("]")
            if not 1 <= n <= MAX_ARRAY:
                raise InvalidProgram("ARRAY_SIZE", token.at, str(n))
            return ArrT(elem, n)
        self.fail("se esperaba un tipo")

    # --- sentencias -----------------------------------------------------------
    def block(self) -> A.Block:
        self.expect("{")
        stmts = []
        while not self.is_("}"):
            if self.tok.kind == "EOF":
                self.fail("bloque sin cerrar")
            stmts.append(self.stmt())
        self.expect("}")
        return A.Block(stmts)

    def stmt(self):
        at = self.tok.at
        if self.accept("let"):
            name = self.ident().text
            self.expect(":")
            ty = self.type_()
            self.expect("=")
            expr = self.expr()
            self.expect(";")
            return A.Let(at, name, ty, expr)
        if self.is_("if"):
            return self.if_stmt()
        if self.accept("while"):
            cond = self.expr()
            return A.While(at, cond, self.block())
        if self.accept("break"):
            self.expect(";")
            return A.Break(at)
        if self.accept("continue"):
            self.expect(";")
            return A.Continue(at)
        if self.accept("return"):
            expr = None if self.is_(";") else self.expr()
            self.expect(";")
            return A.Return(at, expr)
        if self.accept("emit"):
            expr = self.expr()
            self.expect(";")
            return A.Emit(at, expr)
        if self.tok.kind == "IDENT" and self.peek().kind == "OP" and self.peek().text == "(":
            call = self.call()
            self.expect(";")
            return A.ExprStmt(at, call)
        if self.tok.kind == "IDENT":
            name = self.take().text
            index = None
            if self.accept("["):
                index = self.expr()
                self.expect("]")
            self.expect("=")
            expr = self.expr()
            self.expect(";")
            return A.Assign(at, name, index, expr)
        self.fail("se esperaba una sentencia")

    def if_stmt(self) -> A.If:
        at = self.expect("if").at
        cond = self.expr()
        then = self.block()
        els = None
        if self.accept("else"):
            els = self.if_stmt() if self.is_("if") else self.block()
        return A.If(at, cond, then, els)

    # --- expresiones ----------------------------------------------------------
    def expr(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.is_("or"):
            at = self.take().at
            left = A.Binary(at, "or", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.is_("and"):
            at = self.take().at
            left = A.Binary(at, "and", left, self.not_expr())
        return left

    def not_expr(self):
        if self.is_("not"):
            at = self.take().at
            return A.Unary(at, "not", self.not_expr())
        return self.cmp_expr()

    def cmp_expr(self):
        left = self.add_expr()
        if self.tok.kind == "OP" and self.tok.text in CMP_OPS:
            token = self.take()
            left = A.Binary(token.at, token.text, left, self.add_expr())
            if self.tok.kind == "OP" and self.tok.text in CMP_OPS:
                self.fail("las comparaciones no son asociativas")
        return left

    def add_expr(self):
        left = self.mul_expr()
        while self.tok.kind == "OP" and self.tok.text in ("+", "-"):
            token = self.take()
            left = A.Binary(token.at, token.text, left, self.mul_expr())
        return left

    def mul_expr(self):
        left = self.unary()
        while self.tok.kind == "OP" and self.tok.text in ("*", "/", "%"):
            token = self.take()
            left = A.Binary(token.at, token.text, left, self.unary())
        return left

    def unary(self):
        if self.tok.kind == "OP" and self.tok.text == "-":
            if self.version != "0.1" and self.peek().kind in ("INT", "DEC"):
                # CORE v0.2 C2: '-' seguido de un literal es un solo literal negativo (primario).
                at = self.take().at
                literal = self.primary()
                if isinstance(literal, A.IntLit):
                    literal.value = -literal.value
                else:
                    literal.digits = -literal.digits
                literal.at = at
                return self.postfix(literal)
            at = self.take().at
            return A.Unary(at, "-", self.unary())
        return self.postfix()

    def postfix(self, node=None):
        if node is None:
            node = self.primary()
        while True:
            if self.is_("["):
                at = self.take().at
                index = self.expr()
                self.expect("]")
                node = A.Index(at, node, index)
            elif self.is_("as"):
                at = self.take().at
                node = A.Cast(at, node, self.type_())
            else:
                return node

    def call(self) -> A.Call:
        token = self.ident()
        self.expect("(")
        args = []
        if not self.is_(")"):
            while True:
                args.append(self.expr())
                if not self.accept(","):
                    break
        self.expect(")")
        return A.Call(token.at, token.text, args)

    def primary(self):
        token = self.tok
        if token.kind == "INT":
            self.pos += 1
            return A.IntLit(token.at, int(token.text.replace("_", "")))
        if token.kind == "DEC":
            self.pos += 1
            whole, frac = token.text.split(".")
            return A.DecLit(token.at, int(whole + frac), len(frac))
        if self.accept("true"):
            return A.BoolLit(token.at, True)
        if self.accept("false"):
            return A.BoolLit(token.at, False)
        if token.kind == "IDENT":
            if self.peek().kind == "OP" and self.peek().text == "(":
                return self.call()
            self.pos += 1
            return A.Name(token.at, token.text)
        if self.accept("("):
            inner = self.expr()
            self.expect(")")
            return inner
        if self.accept("["):
            first = self.expr()
            if self.accept(";"):
                n = self.nat()
                self.expect("]")
                return A.ArrRep(token.at, first, n)
            elems = [first]
            while self.accept(","):
                elems.append(self.expr())
            self.expect("]")
            return A.ArrLit(token.at, elems)
        self.fail("se esperaba una expresión")


def parse(tokens: list[Token]) -> A.Program:
    return Parser(tokens).program()
