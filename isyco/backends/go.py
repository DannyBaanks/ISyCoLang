"""ISY-IR -> Go autónomo -> binario (ISY_BACKEND/1).

Los *big.Int son valores inmutables: cada operación usa un receptor nuevo.
Arreglos fijos y structs Go se copian por valor; compartir hojas numéricas es
seguro porque nunca se mutan. La aritmética decimal usa enteros escalados.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..ir import ty_from_json
from ..pila import con_pila
from ..types import ArrT, BoolT, DecT, IntT, StrT, StructT, parse_canonical
from .base import ALL_FEATURES, Backend, fn_ident

SABOTAGES = ("half_even_as_half_up", "div_floor", "str_concat_truncates")

RUNTIME = r'''package main

import (
    "fmt"
    "math/big"
    "os"
    "regexp"
    "strconv"
    "strings"
)

type ctx struct {
    steps, maxSteps, depth, maxDepth, emits, maxEmits uint64
    out strings.Builder
}
func end(c *ctx, status, code string) {
    fmt.Fprintf(&c.out, "X %s %s %d\n", status, code, c.steps)
    fmt.Print(c.out.String())
    os.Exit(0)
}
func fail(c *ctx, code string) { end(c, "ERROR", code) }
func tick(c *ctx) { c.steps++; if c.steps > c.maxSteps {end(c, "LIMIT_REACHED", "max_steps")} }
func enter(c *ctx) {
    tick(c)
    if c.depth >= c.maxDepth {end(c, "LIMIT_REACHED", "max_call_depth")}
    c.depth++
}
func emitCheck(c *ctx) {
    if c.emits >= c.maxEmits {end(c, "LIMIT_REACHED", "max_emits")}
    c.emits++
}
// Never write to an operand: numeric leaves are shared across value copies.
func n(s string) *big.Int {
    v, ok := new(big.Int).SetString(s, 10)
    if !ok {panic("invalid generated integer")}
    return v
}
func add(a,b *big.Int) *big.Int {return new(big.Int).Add(a,b)}
func sub(a,b *big.Int) *big.Int {return new(big.Int).Sub(a,b)}
func mul(a,b *big.Int) *big.Int {return new(big.Int).Mul(a,b)}
func neg(a *big.Int) *big.Int {return new(big.Int).Neg(a)}
func fit(c *ctx, v, lo, hi *big.Int, bits uint, mode string) *big.Int {
    if v.Cmp(lo)>=0 && v.Cmp(hi)<=0 {return v}
    if mode=="trap" {fail(c,"OVERFLOW")}
    if mode=="sat" {if v.Cmp(hi)>0 {return hi}; return lo}
    w:=new(big.Int).Lsh(big.NewInt(1),bits)
    return add(new(big.Int).Mod(sub(v,lo),w),lo)
}
func decFit(c *ctx, v,max *big.Int) *big.Int {
    if new(big.Int).Abs(v).Cmp(max)>0 {fail(c,"OVERFLOW")}
    return v
}
func quotient(c *ctx, a,b *big.Int, floor bool) *big.Int {
    if b.Sign()==0 {fail(c,"DIV_ZERO")}
    q,r:=new(big.Int),new(big.Int)
    q.QuoRem(a,b,r)
    if floor && r.Sign()!=0 && a.Sign()!=b.Sign() {return sub(q,big.NewInt(1))}
    return q
}
func remainder(c *ctx, a,b *big.Int) *big.Int {
    if b.Sign()==0 {fail(c,"DIV_ZERO")}
    return new(big.Int).Rem(a,b)
}
func rounded(c *ctx, a,b *big.Int, mode string) *big.Int {
    if b.Sign()==0 {fail(c,"DIV_ZERO")}
    q,r:=new(big.Int),new(big.Int)
    q.QuoRem(a,b,r)
    if r.Sign()==0 {return q}
    if mode=="exact" {fail(c,"INEXACT")}
    if mode=="down" {return q}
    cmp:=mul(new(big.Int).Abs(r),big.NewInt(2)).Cmp(new(big.Int).Abs(b))
    up:=cmp>0 || (cmp==0 && (mode=="half_up" || ISY_TIE))
    if !up {return q}
    sign:=int64(1)
    if a.Sign()!=b.Sign() {sign=-1}
    return add(q,big.NewInt(sign))
}
func fmtDec(v *big.Int, scale int) string {
    if scale==0 {return v.String()}
    s:=new(big.Int).Abs(v).String()
    if len(s)<=scale {s=strings.Repeat("0",scale+1-len(s))+s}
    s=s[:len(s)-scale]+"."+s[len(s)-scale:]
    if v.Sign()<0 {s="-"+s}
    return s
}
func strSet(c *ctx, s string, cap int) string {
    if len(s)>cap {fail(c,"OVERFLOW")}
    return s
}
func cat(c *ctx, a,b string, cap int, truncate bool) string {
    s:=a+b
    if truncate && len(s)>cap {return s[:cap]}
    return strSet(c,s,cap)
}
func index(c *ctx, i *big.Int, size int) int {
    if i.Sign()<0 || i.Cmp(big.NewInt(int64(size)))>=0 {fail(c,"INDEX_OUT_OF_BOUNDS")}
    return int(i.Int64())
}
func slice(c *ctx, s string, lo,hi *big.Int, cap int) string {
    if lo.Sign()<0 || lo.Cmp(hi)>0 || hi.Cmp(big.NewInt(int64(len(s))))>0 {
        fail(c,"INDEX_OUT_OF_BOUNDS")
    }
    return strSet(c,s[int(lo.Int64()):int(hi.Int64())],cap)
}
func chr(c *ctx, v *big.Int) string {
    if !v.IsInt64() {fail(c,"BAD_CHAR")}
    i:=v.Int64()
    if i!=9 && i!=10 && (i<32 || i>126) {fail(c,"BAD_CHAR")}
    return string([]byte{byte(i)})
}
var intPattern=regexp.MustCompile(`^-?(0|[1-9][0-9]*)$`)
func parseInt(c *ctx, s string, lo,hi *big.Int, bits uint, mode string) *big.Int {
    if !intPattern.MatchString(s) || s=="-0" {fail(c,"BAD_FORMAT")}
    return fit(c,n(s),lo,hi,bits,mode)
}
func parseDec(c *ctx, s string, scale int, max *big.Int) *big.Int {
    pattern:=`^-?(0|[1-9][0-9]*)$`
    if scale>0 {pattern=fmt.Sprintf(`^-?(0|[1-9][0-9]*)\.[0-9]{%d}$`,scale)}
    if !regexp.MustCompile(pattern).MatchString(s) {fail(c,"BAD_FORMAT")}
    v:=n(strings.ReplaceAll(s,".",""))
    if strings.HasPrefix(s,"-") && v.Sign()==0 {fail(c,"BAD_FORMAT")}
    return decFit(c,v,max)
}
func parseBool(c *ctx, s string) bool {
    if s=="true" {return true}
    if s=="false" {return false}
    fail(c,"BAD_FORMAT"); return false
}
func escape(s string) string {
    return strings.ReplaceAll(strings.ReplaceAll(s,`\`,`\\`),"\n",`\n`)
}
func out(c *ctx, prefix,s string) {c.out.WriteString(prefix+" "+escape(s)+"\n")}
func limitArg(s string) uint64 {v,e:=strconv.ParseUint(s,10,64); if e!=nil {panic(e)}; return v}
'''


def quoted(text: str) -> str:
    return json.dumps(text, ensure_ascii=True)


def number(value: int) -> str:
    return f'n("{value}")'


class GoEmitter:
    def __init__(self, module: dict, sabotage: str | None = None):
        if sabotage is not None and sabotage not in SABOTAGES:
            raise ValueError(sabotage)
        self.module, self.sabotage = module, sabotage
        self.structs: dict[object, str] = {}
        self.struct_defs: list[str] = []
        self.equalities: dict[object, str] = {}
        self.eq_defs: list[str] = []
        self.lines: list[str] = []
        self.indent, self.tmp = 1, 0

    def gtype(self, t) -> str:
        if isinstance(t, BoolT):
            return "bool"
        if isinstance(t, (IntT, DecT)):
            return "*big.Int"
        if isinstance(t, StrT):
            return "string"
        if isinstance(t, ArrT):
            return f"[{t.n}]{self.gtype(t.elem)}"
        if isinstance(t, StructT):
            if t not in self.structs:
                name = f"S{len(self.structs)}"
                self.structs[t] = name
                fields = "; ".join(f"f_{name} {self.gtype(ft)}" for name, ft in t.fields)
                self.struct_defs.append(f"type {name} struct {{ {fields} }}")
            return self.structs[t]
        raise AssertionError(t)

    def zero(self, t) -> str:
        if isinstance(t, BoolT):
            return "false"
        if isinstance(t, StrT):
            return '""'
        if isinstance(t, (IntT, DecT)):
            return number(0)
        if isinstance(t, StructT):
            return self.gtype(t) + "{" + ", ".join(
                f"f_{name}: {self.zero(ft)}" for name, ft in t.fields) + "}"
        gt = self.gtype(t)
        return f"func() (v {gt}) {{for i := range v {{v[i] = {self.zero(t.elem)}}}; return}}()"

    def put(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def temp(self, value: str) -> str:
        self.tmp += 1
        name = f"t{self.tmp}"
        self.put(f"{name} := {value}; _ = {name}")
        return name

    @staticmethod
    def fit_args(t) -> str:
        return f"{number(t.lo)}, {number(t.hi)}, {t.bits}, {quoted(t.ovf)}"

    def fit(self, t, value: str) -> str:
        if isinstance(t, IntT):
            return f"fit(c, {value}, {self.fit_args(t)})"
        return f"decFit(c, {value}, {number(t.max_m)})"

    def equality(self, t, a: str, b: str) -> str:
        if isinstance(t, (IntT, DecT)):
            return f"({a}.Cmp({b}) == 0)"
        if isinstance(t, (StrT, BoolT)):
            return f"({a} == {b})"
        if t not in self.equalities:
            name = f"eq{len(self.equalities)}"
            self.equalities[t] = name
            gt = self.gtype(t)
            if isinstance(t, ArrT):
                body = f"for i := range a {{if !{self.equality(t.elem, 'a[i]', 'b[i]')} {{return false}}}}; return true"
            else:
                body = "return " + (" && ".join(self.equality(ft, f"a.f_{f}", f"b.f_{f}")
                                               for f, ft in t.fields) or "true")
            self.eq_defs.append(f"func {name}(a,b {gt}) bool {{{body}}}")
        return f"{self.equalities[t]}({a}, {b})"

    def text(self, t, x: str) -> str:
        if isinstance(t, StrT):
            return x
        if isinstance(t, BoolT):
            return f"strconv.FormatBool({x})"
        if isinstance(t, IntT):
            return f"{x}.String()"
        if isinstance(t, DecT):
            return f"fmtDec({x}, {t.s})"
        return self.json_value(t, x)

    def json_value(self, t, x: str, depth: int = 0) -> str:
        if isinstance(t, ArrT):
            i, parts = f"j{depth}", f"parts{depth}"
            item = self.json_value(t.elem, f"{x}[{i}]", depth + 1)
            return (f'func() string {{{parts}:=make([]string,{t.n}); '
                    f'for {i}:=range {parts} {{{parts}[{i}]={item}}}; '
                    f'return "["+strings.Join({parts},",")+"]"}}()')
        if isinstance(t, StructT):
            items = []
            for f, ft in t.fields:
                items.append(quoted(json.dumps(f) + ":") + " + " +
                             self.json_value(ft, f"{x}.f_{f}", depth))
            return ('"{" + ' + ' + "," + '.join(items) + ' + "}"') if items else '"{}"'
        return f"strconv.Quote({self.text(t, x)})"

    def emit(self) -> str:
        bodies = [self.function(fn) for fn in self.module["functions"]]
        main = self.main(next(f for f in self.module["functions"] if f["name"] == "main"))
        tie = "true" if self.sabotage == "half_even_as_half_up" else "q.Bit(0)==1"
        return "\n".join([
            f"// Generated by isyco.backends.go from ISY-IR {self.module['source_sha256']}",
            RUNTIME.replace("ISY_TIE", tie), *self.struct_defs, *self.eq_defs, *bodies, main, ""])

    def function(self, fn: dict) -> str:
        self.lines, self.indent, self.tmp = [], 1, 0
        self.local_types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        params = ["c *ctx"] + [f"l{p} {self.gtype(self.local_types[p])}" for p in fn["params"]]
        ret = ty_from_json(fn["ret"])
        for i, t in enumerate(self.local_types):
            if i not in fn["params"]:
                self.put(f"var l{i} {self.gtype(t)} = {self.zero(t)}; _ = l{i}")
        self.put("enter(c)")
        self.block(fn["body"])
        if ret is None:
            self.put("c.depth--")
        else:
            self.put('panic("unreachable: validated IR requires return")')
        signature = f"func {fn_ident(fn['name'])}({', '.join(params)})"
        if ret is not None:
            signature += " " + self.gtype(ret)
        return signature + " {\n" + "\n".join(self.lines) + "\n}"

    def read_arg(self, t, i: int) -> tuple[str, int]:
        if isinstance(t, ArrT):
            items = []
            for _ in range(t.n):
                expr, i = self.read_arg(t.elem, i)
                items.append(expr)
            return self.gtype(t) + "{" + ",".join(items) + "}", i
        if isinstance(t, StructT):
            items = []
            for f, ft in t.fields:
                expr, i = self.read_arg(ft, i)
                items.append(f"f_{f}: {expr}")
            return self.gtype(t) + "{" + ",".join(items) + "}", i
        if isinstance(t, StrT):
            return f"a[{i}]", i + 1
        if isinstance(t, BoolT):
            return f'(a[{i}] == "1")', i + 1
        return f"n(a[{i}])", i + 1

    def main(self, fn: dict) -> str:
        i, args = 4, []
        for p in fn["params"]:
            arg, i = self.read_arg(ty_from_json(fn["locals"][p]["ty"]), i)
            args.append(arg)
        ret = ty_from_json(fn["ret"])
        call = f"f_main(c{''.join(', ' + a for a in args)})"
        result = call if ret is None else f'r := {call}; out(c,"R",{self.text(ret,"r")})'
        return (f'func main() {{a:=os.Args; if len(a)!={i} {{os.Exit(2)}}; '
                'c:=&ctx{maxSteps:limitArg(a[1]),maxDepth:limitArg(a[2]),maxEmits:limitArg(a[3])}; '
                f'{result}; end(c,"HALTED","-")}}')

    def block(self, stmts: list) -> None:
        for s in stmts:
            self.stmt(s)

    def nested(self, header: str, stmts: list) -> None:
        self.put(header)
        self.indent += 1
        self.block(stmts)
        self.indent -= 1
        self.put("}")

    def stmt(self, s: dict) -> None:
        kind = s["s"]
        self.put(f"tick(c) // {kind} {s['at']}")
        if kind in ("let", "set"):
            self.put(f"l{s['local']} = {self.expr(s['value'])}")
        elif kind in ("set_index", "set_path"):
            path = s.get("path", [{"index": s.get("index")}])
            keys = [self.expr(p["index"]) if "index" in p else None for p in path]
            value = self.expr(s["value"])
            target, t = f"l{s['local']}", self.local_types[s["local"]]
            for p, key in zip(path, keys):
                if "index" in p:
                    k = self.temp(f"index(c,{key},{t.n})")
                    target, t = f"{target}[{k}]", t.elem
                else:
                    target, t = f"{target}.f_{p['field']}", t.field(p["field"])
            self.put(f"{target} = {value}")
        elif kind == "if":
            cond = self.expr(s["cond"])
            self.nested(f"if {cond} {{", s["then"])
            if s["else"] is not None:
                # Go requires } else { on the same line.
                self.lines[-1] += " else {"
                self.indent += 1
                self.block(s["else"])
                self.indent -= 1
                self.put("}")
        elif kind == "while":
            self.put("for {")
            self.indent += 1
            self.put("tick(c)")
            cond = self.expr(s["cond"])
            self.put(f"if !({cond}) {{break}}")
            self.block(s["body"])
            self.indent -= 1
            self.put("}")
        elif kind in ("break", "continue"):
            self.put(kind)
        elif kind == "return":
            value = None if s["value"] is None else self.expr(s["value"])
            self.put("c.depth--")
            self.put("return" if value is None else f"return {value}")
        elif kind == "emit":
            value = self.expr(s["value"])
            self.put("emitCheck(c)")
            self.put(f'out(c,"E",{self.text(ty_from_json(s["value"]["ty"]), value)})')
        elif kind == "call":
            args = [self.expr(a) for a in s["args"]]
            self.put(f"{fn_ident(s['fn'])}(c{''.join(', ' + a for a in args)})")
        else:
            raise AssertionError(kind)

    def expr(self, e: dict) -> str:
        kind, t = e["k"], ty_from_json(e["ty"])
        if kind == "const":
            v = parse_canonical(e["v"], t)
            if isinstance(t, StrT):
                return quoted(v)
            if isinstance(t, BoolT):
                return "true" if v else "false"
            return number(v)
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = [self.expr(a) for a in e["args"]]
            return self.temp(f"{fn_ident(e['fn'])}(c{''.join(', ' + a for a in args)})")
        if kind == "index":
            base, idx = self.expr(e["base"]), self.expr(e["index"])
            bt = ty_from_json(e["base"]["ty"])
            k = self.temp(f"index(c,{idx},len({base}))")
            value = f"{base}[{k}]"
            if isinstance(bt, StrT):
                value = f"big.NewInt(int64({value}))"
            return self.temp(value)
        if kind == "cast":
            return self.cast(e, t)
        if kind == "not":
            return self.temp(f"!({self.expr(e['e'])})")
        if kind == "neg":
            return self.temp(self.fit(t, f"neg({self.expr(e['e'])})"))
        if kind in ("and", "or"):
            result = self.temp(self.expr(e["a"]))
            self.put(f"if {'!' if kind == 'or' else ''}({result}) {{")
            self.indent += 1
            self.put(f"{result} = {self.expr(e['b'])}")
            self.indent -= 1
            self.put("}")
            return result
        if kind == "cmp":
            a, b = self.expr(e["a"]), self.expr(e["b"])
            at = ty_from_json(e["a"]["ty"])
            op = e["op"]
            if op in ("eq", "ne"):
                expr = self.equality(at, a, b)
                return self.temp(expr if op == "eq" else f"!({expr})")
            symbol = {"lt": "<", "le": "<=", "gt": ">", "ge": ">="}[op]
            expr = f"{a} {symbol} {b}" if isinstance(at, StrT) else f"{a}.Cmp({b}) {symbol} 0"
            return self.temp(expr)
        if kind == "bin":
            a, b = self.expr(e["a"]), self.expr(e["b"])
            op = e["op"]
            if op in ("add", "sub", "mul"):
                value = f"{op}({a},{b})"
            elif op == "rem":
                value = f"remainder(c,{a},{b})"
            else:
                value = f"quotient(c,{a},{b},{str(self.sabotage == 'div_floor').lower()})"
            if isinstance(t, DecT) and op in ("mul", "div"):
                num, den = (value, number(10 ** t.s)) if op == "mul" else (f"mul({a},{number(10 ** t.s)})", b)
                value = f"rounded(c,{num},{den},{quoted(t.rnd)})"
            return self.temp(self.fit(t, value))
        if kind == "array":
            items = [self.expr(item) for item in e["elems"]]
            return self.temp(self.gtype(t) + "{" + ",".join(items) + "}")
        if kind == "repeat":
            value = self.expr(e["elem"])
            gt = self.gtype(t)
            return self.temp(f"func() (v {gt}) {{for i:=range v {{v[i]={value}}};return}}()")
        if kind == "concat":
            a, b = self.expr(e["a"]), self.expr(e["b"])
            truncate = str(self.sabotage == "str_concat_truncates").lower()
            return self.temp(f"cat(c,{a},{b},{t.n},{truncate})")
        if kind == "widen":
            return self.temp(f"strSet(c,{self.expr(e['e'])},{t.n})")
        if kind == "len":
            return self.temp(f"big.NewInt(int64(len({self.expr(e['e'])})))")
        if kind == "slice":
            x, lo, hi = self.expr(e["e"]), self.expr(e["lo"]), self.expr(e["hi"])
            return self.temp(f"slice(c,{x},{lo},{hi},{t.n})")
        if kind == "chr":
            return self.temp(f"chr(c,{self.expr(e['e'])})")
        if kind == "field":
            return self.temp(f"{self.expr(e['base'])}.f_{e['name']}")
        if kind == "struct":
            fields = [f"f_{item['name']}: {self.expr(item['value'])}" for item in e["fields"]]
            return self.temp(self.gtype(t) + "{" + ",".join(fields) + "}")
        raise AssertionError(kind)

    def cast(self, e: dict, dst) -> str:
        x, src = self.expr(e["e"]), ty_from_json(e["e"]["ty"])
        if isinstance(dst, StrT):
            return self.temp(f"strSet(c,{self.text(src,x)},{dst.n})")
        if isinstance(src, StrT):
            if isinstance(dst, BoolT):
                value = f"parseBool(c,{x})"
            elif isinstance(dst, IntT):
                value = f"parseInt(c,{x},{self.fit_args(dst)})"
            else:
                value = f"parseDec(c,{x},{dst.s},{number(dst.max_m)})"
            return self.temp(value)
        if isinstance(src, IntT) and isinstance(dst, IntT):
            value = x
        elif isinstance(src, IntT):
            value = f"mul({x},{number(10 ** dst.s)})"
        elif isinstance(dst, IntT):
            value = f"quotient(c,{x},{number(10 ** src.s)},false)"
        else:
            value = f"rounded(c,mul({x},{number(10 ** dst.s)}),{number(10 ** src.s)},{quoted(dst.rnd)})"
        return self.temp(self.fit(dst, value))


class GoBackend(Backend):
    name = "go"
    extension = ".go"
    features = ALL_FEATURES
    sabotages = SABOTAGES
    # Go includes its own allocator, GC and growing goroutine stacks.
    rss_ceiling_kb = 64_000

    def toolchain(self) -> str | None:
        compiler = shutil.which("go")
        if not compiler:
            return None
        proc = subprocess.run([compiler, "version"], capture_output=True, text=True)
        return f"{compiler}: {proc.stdout.strip()}" if proc.returncode == 0 else None

    @con_pila
    def emit(self, module: dict, sabotage: str | None = None) -> str:
        return GoEmitter(module, sabotage).emit()

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        return ["go", "build", *extra_flags, "-o", str(binary), str(source)]


BACKEND = GoBackend()
