"""Parser de descenso recursivo para la gramática de spec §2.1."""
from __future__ import annotations

import copy

from . import ast as A
from .errors import InvalidProgram
from .lexer import Token
from .types import INT_ALIASES, MAX_STR, ArrT, BoolT, ContextStrT, DecT, IntT, NamedT, StrT
from .versions import SUPPORTED, has

CMP_OPS = {"==", "!=", "<", "<=", ">", ">="}
ROUND_MODES = {"half_even", "half_up", "down", "exact"}
MAX_ARRAY = 65536
SUPPORTED_VERSIONS = set(SUPPORTED)


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.version = "0.1"
        self.no_struct_lit = False   # en condiciones de if/while (CORE v0.3 §3.2, P4)
        #: V2: nombres ya escritos en este módulo, para que el índice sintético no choque
        self.usados = {t.text for t in tokens if t.kind in ("IDENT", "KW")}
        self.for_n = 0

    @property
    def v03(self) -> bool:
        return has(self.version, "v03")

    @property
    def v04(self) -> bool:
        return has(self.version, "v04")

    @property
    def v05(self) -> bool:
        return has(self.version, "v05")

    def is_qualified(self) -> bool:
        """CORE v0.4: `x.f(`, `x.S {` o `x.S` en un tipo son nombres calificados."""
        return (self.v04 and self.tok.kind == "IDENT" and self.peek().kind == "OP"
                and self.peek().text == "." and self.peek(2).kind == "IDENT")

    def qname(self) -> str:
        module = self.take().text
        self.expect(".")
        return f"{module}.{self.ident().text}"

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
        structs: dict[str, A.StructDecl] = {}
        imports: list[A.Import] = []
        public: set[str] = set()
        while self.v04 and self.is_("import"):
            at = self.take().at
            path = [self.ident().text]
            while self.accept("."):
                path.append(self.ident().text)
            self.expect(";")
            imports.append(A.Import(at, tuple(path)))
        while self.tok.kind != "EOF":
            is_pub = self.v04 and self.accept("pub")
            if is_pub and not (self.is_("fn") or self.is_("struct")):
                self.fail("pub solo antecede a fn o struct")
            if self.v04 and self.is_("import"):
                self.fail("los import van antes de toda declaración")
            if self.v03 and self.is_("struct"):
                decl = self.struct_decl()
                if decl.name in structs or decl.name in fns:
                    raise InvalidProgram("DUPLICATE_NAME", decl.at, decl.name)
                structs[decl.name] = decl
                if is_pub:
                    public.add(decl.name)
                continue
            fn = self.fn_decl()
            if fn.name in fns or fn.name in structs:
                raise InvalidProgram("DUPLICATE_NAME", fn.at, fn.name)
            fns[fn.name] = fn
            if is_pub:
                public.add(fn.name)
        return A.Program(fns, self.version, structs, imports, public)

    def struct_decl(self) -> A.StructDecl:
        at = self.expect("struct").at
        name = self.ident().text
        self.expect("{")
        fields, seen = [], set()
        while True:
            ftok = self.ident()
            self.expect(":")
            if ftok.text in seen:
                raise InvalidProgram("DUPLICATE_NAME", ftok.at, ftok.text)
            seen.add(ftok.text)
            fields.append((ftok.text, self.type_(), ftok.at))
            if not self.accept(",") or self.is_("}"):
                break
        self.expect("}")
        return A.StructDecl(at, name, fields)

    def fn_decl(self) -> A.Fn:
        at = self.expect("fn").at
        name = self.ident().text
        self.expect("(")
        params = []
        if not self.is_(")"):
            while True:
                ptok = self.ident()
                self.expect(":")
                params.append((ptok.text, self.type_(bare_str=True), ptok.at))
                if not self.accept(","):
                    break
        self.expect(")")
        ret = self.type_(bare_str=True) if self.accept("->") else None
        emits = False
        if self.accept("!"):
            self.expect("emit")
            emits = True
        return A.Fn(at, name, params, ret, emits, self.block())

    # --- tipos ----------------------------------------------------------------
    def type_(self, bare_str: bool = False):
        """`bare_str` (CORE v0.5 V6/V6-bis): en parámetros y en el retorno se acepta
        `str` sin capacidad. En cualquier otra posición sigue siendo `SYNTAX`."""
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
        if self.v03 and self.accept("str"):
            if not self.is_("<"):
                # V6/V6-bis: `str` pelado NO es «capacidad infinita»; es una capacidad
                # diferida que solo existe en un parámetro (V6) o en el retorno (V6-bis),
                # y solo a partir de 0.5.
                if not (bare_str and self.v05):
                    self.fail("str necesita su capacidad: str<N>")
                return ContextStrT()
            self.expect("<")
            n = self.nat()
            self.expect(">")
            if not 1 <= n <= MAX_STR:
                raise InvalidProgram("STR_SIZE", token.at, str(n))
            return StrT(n)
        if self.is_qualified():
            return NamedT(self.qname(), token.at)
        if self.v03 and token.kind == "IDENT":
            self.pos += 1
            return NamedT(token.text, token.at)
        if self.accept("["):
            elem = self.type_()
            if isinstance(elem, ArrT):
                raise InvalidProgram("SYNTAX", token.at, "los arreglos no contienen arreglos")
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
            sentencia = self.stmt()
            if isinstance(sentencia, list):    # V2: el azúcar `for` expande a dos sentencias
                stmts.extend(sentencia)
            else:
                stmts.append(sentencia)
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
            cond = self.cond()
            return A.While(at, cond, self.block())
        if self.v05 and self.accept("for"):
            return self.for_stmt(at)
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
        if (self.tok.kind == "IDENT" and self.peek().kind == "OP" and self.peek().text == "(") \
                or (self.is_qualified() and self.peek(3).kind == "OP" and self.peek(3).text == "("):
            call = self.call()
            self.expect(";")
            return A.ExprStmt(at, call)
        if self.tok.kind == "IDENT":
            name = self.take().text
            path = []
            while True:
                if self.accept("["):
                    path.append(("index", self.expr()))
                    self.expect("]")
                elif self.v03 and self.accept("."):
                    path.append(("field", self.ident().text))
                else:
                    break
            self.expect("=")
            expr = self.expr()
            self.expect(";")
            if len(path) > 1 or any(kind == "field" for kind, _ in path):
                return A.AssignPath(at, name, path, expr)
            return A.Assign(at, name, path[0][1] if path else None, expr)
        self.fail("se esperaba una sentencia")

    def if_stmt(self) -> A.If:
        at = self.expect("if").at
        cond = self.cond()
        then = self.block()
        els = None
        if self.accept("else"):
            els = self.if_stmt() if self.is_("if") else self.block()
        return A.If(at, cond, then, els)

    # --- azúcar CORE v0.5 ------------------------------------------------------
    def for_stmt(self, at) -> list:
        """CORE v0.5 V2: `for x in a { … }` se expande aquí, no en el lowering.

        El AST que recibe la referencia es el `while` gemelo escrito a mano en
        `programs/conformance_v0.5/gemelos/`, así que `steps`, límites y trazas quedan
        definidos sin regla nueva. El incremento va ANTES del cuerpo porque es medido: con
        el incremento abajo, el `continue` salta el avance —
        `gemelos/404_while_incremento_abajo.isy` (cabecera `0.4`, corre hoy) termina en
        `LIMIT_REACHED(max_steps)` con `emits=["2","3"]`. La cota se escribe `len(a)` y la
        resuelve V1 en el checker: el azúcar no pide ninguna capacidad nueva.
        """
        variable = self.ident().text
        if not (self.tok.kind == "IDENT" and self.tok.text == "in"):
            self.fail("se esperaba 'in' en el for")     # V3: `in` es contextual, no KW
        self.take()
        # un LUGAR (`xs`, `p.xs`), no `expr()`: `xs {` es la sintaxis de un literal de struct,
        # y una llamada o un literal evaluados dos veces (cota e índice) cambiarían los efectos.
        lugar = A.Name(self.tok.at, self.ident().text)
        while self.is_(".") and self.peek().kind == "IDENT":
            self.take()
            lugar = A.Field(lugar.at, lugar, self.ident().text)
        cuerpo = self.block()
        i = self.fresh_index()
        cond = A.Binary(at, "<", A.Binary(at, "+", A.Name(at, i), A.IntLit(at, 1)),
                        A.Len(at, copy.deepcopy(lugar)))
        # Las llaves del `while` gemelo son notacionales: el lenguaje no tiene sentencias-bloque,
        # así que las dos sentencias se escriben en el bloque contenedor. Eso es seguro porque
        # `fresh_index` produce un nombre que ningún fuente de este módulo puede contener.
        # El `-1` es `IntLit`, no `Unary`: CORE v0.2 C2 ya define `-1` como un solo literal, y
        # construirlo con el operador restaba un `neg` en la IR que el gemelo escrito a mano no tiene.
        return [A.Let(at, i, INT_ALIASES["i64"], A.IntLit(at, -1)),
                A.While(at, cond, A.Block([
                    A.Assign(at, i, None, A.Binary(at, "+", A.Name(at, i), A.IntLit(at, 1))),
                    A.Let(at, variable, None, A.Index(at, copy.deepcopy(lugar), A.Name(at, i))),
                    *cuerpo.stmts]))]

    def fresh_index(self) -> str:
        """Índice sintético del `for`: no puede chocar con un nombre escrito, porque se
        elige fuera del conjunto de identificadores del módulo y el contador avanza."""
        while f"foridx{self.for_n}" in self.usados:
            self.for_n += 1
        nombre = f"foridx{self.for_n}"
        self.for_n += 1
        return nombre

    # --- expresiones ----------------------------------------------------------
    def cond(self):
        saved, self.no_struct_lit = self.no_struct_lit, True
        try:
            return self.expr()
        finally:
            self.no_struct_lit = saved

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
            if has(self.version, "v02") and self.peek().kind in ("INT", "DEC"):
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
            elif self.v03 and self.is_("."):
                at = self.take().at
                node = A.Field(at, node, self.ident().text)
            else:
                return node

    def call(self) -> A.Call:
        token = self.tok
        name = self.qname() if self.is_qualified() else self.ident().text
        self.expect("(")
        args = []
        if not self.is_(")"):
            while True:
                args.append(self.expr())
                if not self.accept(","):
                    break
        self.expect(")")
        return A.Call(token.at, name, args)

    def primary(self):
        token = self.tok
        if token.kind == "INT":
            self.pos += 1
            return A.IntLit(token.at, int(token.text.replace("_", "")))
        if token.kind == "DEC":
            self.pos += 1
            whole, frac = token.text.split(".")
            return A.DecLit(token.at, int(whole + frac), len(frac))
        if token.kind == "STR":
            self.pos += 1
            return A.StrLit(token.at, token.text)
        if self.v03 and token.kind == "KW" and token.text in ("len", "slice", "chr"):
            self.pos += 1
            self.expect("(")
            args = [self.expr()]
            while self.accept(","):
                args.append(self.expr())
            self.expect(")")
            arity = {"len": 1, "slice": 3, "chr": 1}[token.text]
            if len(args) != arity:
                raise InvalidProgram("SYNTAX", token.at, f"{token.text} recibe {arity} argumentos")
            if token.text == "len":
                return A.Len(token.at, args[0])
            if token.text == "chr":
                return A.Chr(token.at, args[0])
            return A.Slice(token.at, *args)
        if self.accept("true"):
            return A.BoolLit(token.at, True)
        if self.accept("false"):
            return A.BoolLit(token.at, False)
        if self.is_qualified() and self.peek(3).kind == "OP" and self.peek(3).text in ("(", "{"):
            if self.peek(3).text == "(":
                return self.call()
            if not self.no_struct_lit:
                return self.struct_lit()
        if token.kind == "IDENT":
            if self.peek().kind == "OP" and self.peek().text == "(":
                return self.call()
            if (self.v03 and not self.no_struct_lit and self.peek().kind == "OP"
                    and self.peek().text == "{"):
                return self.struct_lit()
            self.pos += 1
            return A.Name(token.at, token.text)
        if self.accept("("):
            saved, self.no_struct_lit = self.no_struct_lit, False
            try:
                inner = self.expr()
            finally:
                self.no_struct_lit = saved
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


    def struct_lit(self) -> A.StructLit:
        token = self.tok
        name = self.qname() if self.is_qualified() else self.ident().text
        self.expect("{")
        fields = []
        while not self.is_("}"):
            ftok = self.ident()
            self.expect(":")
            fields.append((ftok.text, self.expr(), ftok.at))
            if not self.accept(","):
                break
        self.expect("}")
        return A.StructLit(token.at, name, fields)


def parse(tokens: list[Token]) -> A.Program:
    return Parser(tokens).program()
