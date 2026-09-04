"""Tareas del banco de pruebas.

Cada tarea es una peticion en lenguaje normal y una comprobacion que mira el
disco. No se juzga lo que la IA dice haber hecho, sino lo que quedo hecho: es
la unica forma de medir capacidad sin engañarse.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["TASKS", "Task", "by_name", "by_tag"]


@dataclass
class Task:
    name: str
    prompt: str
    check: Callable[[Path], tuple[bool, str]]
    # Estado del que parte la tarea: archivos que se crean antes de empezar.
    setup: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    # Turnos que se le permiten. Una tarea de varios pasos necesita más.
    max_turns: int = 10


def _leer(raiz: Path, ruta: str) -> str:
    archivo = raiz / ruta
    return archivo.read_text(errors="replace") if archivo.is_file() else ""


# ---------------------------------------------------------------------------
# Archivos
# ---------------------------------------------------------------------------


def _check_carpeta(raiz: Path) -> tuple[bool, str]:
    carpeta = raiz / "notas"
    if not carpeta.is_dir():
        return False, "no existe la carpeta notas/"
    readme = carpeta / "README.md"
    if not readme.is_file():
        return False, "existe notas/ pero no notas/README.md"
    if not readme.read_text().strip():
        return False, "el README está vacío"
    return True, "carpeta y README creados"


def _check_renombrado(raiz: Path) -> tuple[bool, str]:
    if (raiz / "viejo.txt").exists():
        return False, "viejo.txt sigue ahí"
    nuevo = raiz / "nuevo.txt"
    if not nuevo.is_file():
        return False, "no existe nuevo.txt"
    if "contenido original" not in nuevo.read_text():
        return False, "nuevo.txt no conserva el contenido"
    return True, "renombrado conservando el contenido"


def _check_busqueda(raiz: Path) -> tuple[bool, str]:
    respuesta = _leer(raiz, "RESPUESTA.txt").lower()
    if not respuesta:
        return False, "no escribió RESPUESTA.txt"
    if "config/ajustes.json" in respuesta or "ajustes.json" in respuesta:
        return True, "encontró la ruta correcta"
    return False, f"ruta incorrecta: {respuesta.strip()[:80]}"


def _check_conteo(raiz: Path) -> tuple[bool, str]:
    respuesta = _leer(raiz, "RESPUESTA.txt").strip()
    if not respuesta:
        return False, "no escribió RESPUESTA.txt"
    # Hay 3 archivos .py en el montaje.
    return ("3" in respuesta, f"respondió: {respuesta[:60]}")


# ---------------------------------------------------------------------------
# Código
# ---------------------------------------------------------------------------


def _check_bug(raiz: Path) -> tuple[bool, str]:
    codigo = _leer(raiz, "calculadora.py")
    if not codigo:
        return False, "calculadora.py desapareció"
    # La prueba de verdad: ejecutarlo.
    import subprocess

    proc = subprocess.run(
        ["python3", "-c",
         "import sys; sys.path.insert(0, '.'); "
         "from calculadora import media; "
         "assert media([2, 4, 6]) == 4, media([2, 4, 6]); "
         "assert media([]) == 0, 'lista vacía debería dar 0'; "
         "print('bien')"],
        cwd=raiz, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode == 0:
        return True, "media() corregida y funcionando"
    return False, (proc.stderr or proc.stdout).strip().splitlines()[-1][:120]


def _check_test(raiz: Path) -> tuple[bool, str]:
    import subprocess

    proc = subprocess.run(
        ["python3", "-m", "pytest", "-q", "test_saludo.py"],
        cwd=raiz, capture_output=True, text=True, timeout=60,
    )
    if proc.returncode == 0:
        return True, "el test pasa"
    return False, (proc.stdout or proc.stderr).strip().splitlines()[-1][:120]


def _check_funcion_nueva(raiz: Path) -> tuple[bool, str]:
    import subprocess

    proc = subprocess.run(
        ["python3", "-c",
         "import sys; sys.path.insert(0, '.'); "
         "from utilidades import es_palindromo; "
         "assert es_palindromo('anilina'); "
         "assert es_palindromo('Anita lava la tina'); "
         "assert not es_palindromo('hola mundo'); "
         "print('bien')"],
        cwd=raiz, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode == 0:
        return True, "es_palindromo() escrita y correcta"
    return False, (proc.stderr or proc.stdout).strip().splitlines()[-1][:120]


# ---------------------------------------------------------------------------
# Varios pasos
# ---------------------------------------------------------------------------


def _check_refactor(raiz: Path) -> tuple[bool, str]:
    codigo = _leer(raiz, "informe.py")
    if "print(" in codigo:
        return False, "sigue habiendo print() en informe.py"
    if "logging" not in codigo:
        return False, "no usa logging"
    import subprocess

    proc = subprocess.run(["python3", "-c", "import informe"],
                          cwd=raiz, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return False, "el módulo ya no importa: " + proc.stderr.strip()[-100:]
    return True, "print() sustituidos por logging y el módulo importa"


def _check_convenciones(raiz: Path) -> tuple[bool, str]:
    """Comprueba que respetó el AGENTS.md del proyecto."""
    codigo = _leer(raiz, "saludos.py")
    if "def saludar" not in codigo:
        return False, "no escribió saludar()"
    # El AGENTS.md pide comentarios en español y sin abreviaturas.
    if not any(p in codigo.lower() for p in ("español", "saluda", "devuelve", "nombre")):
        return False, "no hay comentarios o docstring en español"
    if '"""' not in codigo and "'''" not in codigo:
        return False, "sin docstring, que el AGENTS.md pide"
    return True, "respetó las convenciones del AGENTS.md"


TASKS: list[Task] = [
    Task(
        name="crear-carpeta",
        prompt="Crea una carpeta llamada notas y dentro un README.md que "
               "explique en dos líneas para qué sirve esa carpeta.",
        check=_check_carpeta,
        tags=("archivos", "facil"),
        max_turns=6,
    ),
    Task(
        name="renombrar",
        prompt="Renombra viejo.txt a nuevo.txt sin perder su contenido.",
        setup={"viejo.txt": "contenido original que no se debe perder\n"},
        check=_check_renombrado,
        tags=("archivos", "facil"),
        max_turns=6,
    ),
    Task(
        name="buscar-archivo",
        prompt="¿Dónde está el archivo de configuración de este proyecto? "
               "Escribe su ruta relativa en un archivo RESPUESTA.txt.",
        setup={
            "config/ajustes.json": '{"tema": "oscuro"}\n',
            "src/main.py": "print('hola')\n",
            "docs/guia.md": "# Guía\n",
        },
        check=_check_busqueda,
        tags=("busqueda", "facil"),
        max_turns=8,
    ),
    Task(
        name="contar-archivos",
        prompt="¿Cuántos archivos .py hay en este proyecto, contando "
               "subcarpetas? Escribe solo el número en RESPUESTA.txt.",
        setup={
            "a.py": "x = 1\n",
            "src/b.py": "y = 2\n",
            "src/hondo/c.py": "z = 3\n",
            "leeme.md": "no soy python\n",
        },
        check=_check_conteo,
        tags=("busqueda", "facil"),
        max_turns=8,
    ),
    Task(
        name="arreglar-bug",
        prompt="La función media() de calculadora.py falla con una lista "
               "vacía. Arréglala para que devuelva 0 en ese caso, sin "
               "cambiar lo demás.",
        setup={
            "calculadora.py": (
                "def media(numeros):\n"
                "    return sum(numeros) / len(numeros)\n"
            ),
        },
        check=_check_bug,
        tags=("codigo", "medio"),
        max_turns=10,
    ),
    Task(
        name="arreglar-test",
        prompt="El test de este proyecto falla. Averigua por qué y arréglalo "
               "tocando el código, no el test.",
        setup={
            "saludo.py": "def saludar(nombre):\n    return f'Hola {nombre}'\n",
            "test_saludo.py": (
                "from saludo import saludar\n\n"
                "def test_saludo():\n"
                "    assert saludar('Ana') == '¡Hola, Ana!'\n"
            ),
        },
        check=_check_test,
        tags=("codigo", "medio"),
        max_turns=12,
    ),
    Task(
        name="funcion-nueva",
        prompt="Escribe en utilidades.py una función es_palindromo(texto) que "
               "diga si un texto es palíndromo, ignorando espacios, mayúsculas "
               "y acentos. 'Anita lava la tina' debe dar True.",
        check=_check_funcion_nueva,
        tags=("codigo", "medio"),
        max_turns=10,
    ),
    Task(
        name="refactor",
        prompt="En informe.py, sustituye todos los print() por logging, "
               "manteniendo los mismos mensajes. El módulo debe seguir "
               "importándose sin errores.",
        setup={
            "informe.py": (
                "def generar(datos):\n"
                "    print('empezando el informe')\n"
                "    total = sum(datos)\n"
                "    print(f'total: {total}')\n"
                "    return total\n"
            ),
        },
        check=_check_refactor,
        tags=("codigo", "dificil"),
        max_turns=12,
    ),
    Task(
        name="respetar-convenciones",
        prompt="Escribe en saludos.py una función saludar(nombre) que "
               "devuelva un saludo.",
        setup={
            "AGENTS.md": (
                "# Convenciones de este proyecto\n\n"
                "- Toda función lleva docstring, escrito en español.\n"
                "- Los comentarios van en español, sin abreviaturas.\n"
            ),
        },
        check=_check_convenciones,
        tags=("contexto", "medio"),
        max_turns=8,
    ),
]


def by_name(nombre: str) -> Task | None:
    return next((t for t in TASKS if t.name == nombre), None)


def by_tag(tag: str) -> list[Task]:
    return [t for t in TASKS if tag in t.tags]
