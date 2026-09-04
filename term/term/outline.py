"""Esqueleto del codigo: que clases y funciones hay, y con que firma.

Un mapa de nombres de archivo sirve para saber que existe, pero no para saber
que hace. Con las firmas, el modelo puede llamar a una funcion sin que le
pasemos el archivo entero, que es lo que de verdad gasta contexto y dinero.

Python se lee con `ast`, que viene en la biblioteca estandar y no se equivoca.
Los demas lenguajes se leen con patrones: no es un analisis de verdad, pero
saca las declaraciones de nivel superior, que es el noventa por ciento de lo
que hace falta. Si `tree_sitter` esta instalado tampoco se usa: no compensa
imponer quince dependencias por el diez por ciento restante.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Symbol", "build_outline", "extract", "outline_file"]

# Tope por archivo. Un archivo con trescientas funciones no aporta trescientas
# lineas de valor.
_MAX_PER_FILE = 40
_MAX_BYTES = 400_000


@dataclass(frozen=True)
class Symbol:
    kind: str          # clase | funcion | metodo | constante
    name: str
    signature: str
    line: int
    doc: str = ""

    def render(self, indent: str = "  ") -> str:
        sangria = indent * (2 if self.kind == "metodo" else 1)
        texto = f"{sangria}{self.signature}"
        if self.doc:
            texto += f"  — {self.doc}"
        return texto


# ---------------------------------------------------------------------------
# Python: con el analizador de verdad
# ---------------------------------------------------------------------------


def _firma_python(nodo: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    partes: list[str] = []
    args = nodo.args

    posicionales = [*args.posonlyargs, *args.args]
    defectos = list(args.defaults)
    # Los valores por defecto se alinean por la derecha.
    relleno = [None] * (len(posicionales) - len(defectos))
    for arg, defecto in zip(posicionales, relleno + defectos, strict=False):
        texto = arg.arg
        if arg.annotation is not None:
            texto += f": {ast.unparse(arg.annotation)}"
        if defecto is not None:
            texto += f" = {ast.unparse(defecto)}"
        partes.append(texto)

    if args.vararg:
        partes.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        partes.append("*")
    for arg, defecto in zip(args.kwonlyargs, args.kw_defaults, strict=False):
        texto = arg.arg
        if arg.annotation is not None:
            texto += f": {ast.unparse(arg.annotation)}"
        if defecto is not None:
            texto += f" = {ast.unparse(defecto)}"
        partes.append(texto)
    if args.kwarg:
        partes.append(f"**{args.kwarg.arg}")

    prefijo = "async def" if isinstance(nodo, ast.AsyncFunctionDef) else "def"
    firma = f"{prefijo} {nodo.name}({', '.join(partes)})"
    if nodo.returns is not None:
        firma += f" -> {ast.unparse(nodo.returns)}"
    return firma


def _resumen_doc(nodo) -> str:
    """Primera linea del docstring, que suele decir para que sirve."""
    texto = ast.get_docstring(nodo)
    if not texto:
        return ""
    primera = texto.strip().splitlines()[0].strip()
    return primera[:80]


def _extraer_python(codigo: str) -> list[Symbol]:
    try:
        arbol = ast.parse(codigo)
    except SyntaxError:
        return []

    simbolos: list[Symbol] = []
    for nodo in arbol.body:
        if isinstance(nodo, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in nodo.bases)
            firma = f"class {nodo.name}({bases})" if bases else f"class {nodo.name}"
            simbolos.append(Symbol("clase", nodo.name, firma, nodo.lineno,
                                   _resumen_doc(nodo)))
            for hijo in nodo.body:
                if isinstance(hijo, ast.FunctionDef | ast.AsyncFunctionDef):
                    # Lo privado no le interesa a quien llama desde fuera.
                    if hijo.name.startswith("_") and not hijo.name.startswith("__"):
                        continue
                    simbolos.append(Symbol(
                        "metodo", hijo.name, _firma_python(hijo), hijo.lineno,
                        _resumen_doc(hijo)))
        elif isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
            if nodo.name.startswith("_"):
                continue
            simbolos.append(Symbol("funcion", nodo.name, _firma_python(nodo),
                                   nodo.lineno, _resumen_doc(nodo)))
        elif isinstance(nodo, ast.Assign):
            # Solo las constantes de modulo, que suelen ser configuracion.
            for destino in nodo.targets:
                if isinstance(destino, ast.Name) and destino.id.isupper():
                    simbolos.append(Symbol("constante", destino.id,
                                           destino.id, nodo.lineno))
    return simbolos


# ---------------------------------------------------------------------------
# Los demas lenguajes: por patrones
# ---------------------------------------------------------------------------

# Cada patron captura la declaracion entera en el grupo 0 y el nombre en el 1.
_PATRONES: dict[str, list[tuple[str, str]]] = {
    "js": [
        ("clase", r"^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)[^\{]*"),
        ("funcion", r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\([^)]*\)"),
        ("funcion", r"^\s*(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"),
        ("constante", r"^\s*(?:export\s+)?const\s+([A-Z][A-Z0-9_]+)\s*="),
    ],
    "ts": [
        ("interfaz", r"^\s*(?:export\s+)?interface\s+(\w+)[^\{]*"),
        ("tipo", r"^\s*(?:export\s+)?type\s+(\w+)\s*="),
    ],
    "go": [
        ("funcion", r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\([^)]*\)[^\{]*"),
        ("tipo", r"^type\s+(\w+)\s+(?:struct|interface)"),
    ],
    "rust": [
        ("funcion", r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)[^\{]*"),
        ("tipo", r"^\s*(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)"),
    ],
    "java": [
        ("clase", r"^\s*(?:public\s+|abstract\s+|final\s+)*(?:class|interface|enum)\s+(\w+)"),
        ("metodo", r"^\s+(?:public|protected)\s+[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)"),
    ],
    "ruby": [
        ("clase", r"^\s*(?:class|module)\s+(\w+)"),
        ("metodo", r"^\s*def\s+([\w.?!]+)"),
    ],
    "php": [
        ("clase", r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+(\w+)"),
        ("funcion", r"^\s*(?:public\s+|private\s+|protected\s+|static\s+)*function\s+(\w+)\s*\([^)]*\)"),
    ],
    "sh": [
        ("funcion", r"^\s*(?:function\s+)?(\w+)\s*\(\s*\)\s*\{"),
    ],
}

_EXT_A_LENGUAJE = {
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
    ".ts": "ts", ".tsx": "ts",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "java",
    ".rb": "ruby", ".php": "php", ".sh": "sh", ".bash": "sh",
    ".c": "rust", ".h": "rust", ".cpp": "rust", ".hpp": "rust", ".cs": "java",
    ".swift": "rust",
}


def _extraer_por_patrones(codigo: str, lenguaje: str) -> list[Symbol]:
    patrones = list(_PATRONES.get(lenguaje, []))
    # TypeScript es JavaScript con extras.
    if lenguaje == "ts":
        patrones += _PATRONES["js"]
    if not patrones:
        return []

    simbolos: list[Symbol] = []
    vistos: set[str] = set()
    for numero, linea in enumerate(codigo.splitlines(), 1):
        if len(linea) > 400:
            continue
        for tipo, patron in patrones:
            match = re.match(patron, linea)
            if not match:
                continue
            nombre = match.group(1)
            if nombre in vistos:
                break
            vistos.add(nombre)
            simbolos.append(Symbol(
                tipo, nombre, " ".join(match.group(0).split()).rstrip("{").strip(),
                numero))
            break
    return simbolos


# ---------------------------------------------------------------------------
# Fachada
# ---------------------------------------------------------------------------


def extract(path: Path | str) -> list[Symbol]:
    """Simbolos de un archivo, vacio si no se sabe leerlo."""
    ruta = Path(path)
    try:
        if ruta.stat().st_size > _MAX_BYTES:
            return []
        codigo = ruta.read_text(errors="replace")
    except OSError:
        return []

    if ruta.suffix == ".py":
        simbolos = _extraer_python(codigo)
    else:
        lenguaje = _EXT_A_LENGUAJE.get(ruta.suffix)
        simbolos = _extraer_por_patrones(codigo, lenguaje) if lenguaje else []
    return simbolos[:_MAX_PER_FILE]


def outline_file(path: Path | str, *, with_docs: bool = True) -> str:
    """Esqueleto de un archivo, listo para leer."""
    simbolos = extract(path)
    if not simbolos:
        return ""
    lineas = [f"{path}:"]
    for simbolo in simbolos:
        texto = simbolo.render()
        if not with_docs and "  — " in texto:
            texto = texto.split("  — ")[0]
        lineas.append(texto)
    return "\n".join(lineas)


def build_outline(
    archivos: list[Path | str], *, budget: int = 12_000, with_docs: bool = True,
) -> str:
    """Esqueleto de varios archivos, sin pasarse del presupuesto de caracteres.

    El tope existe porque esto va dentro del prompt de cada turno: un esqueleto
    sin limite costaria mas que los archivos que pretende ahorrar.
    """
    partes: list[str] = []
    total = 0
    for archivo in archivos:
        bloque = outline_file(archivo, with_docs=with_docs)
        if not bloque:
            continue
        if total + len(bloque) > budget:
            partes.append(f"… y {len(archivos) - len(partes)} archivos más")
            break
        partes.append(bloque)
        total += len(bloque)
    return "\n\n".join(partes)
