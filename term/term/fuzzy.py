"""Busqueda difusa de archivos, al estilo de fzf.

Escribes trozos sueltos del nombre y aparece lo que buscas: `tesses` encuentra
`tests/test_session.py`. La puntuacion premia lo que de verdad distingue un
acierto bueno de uno casual: que las letras vayan seguidas, que caigan al
principio de una palabra y que esten en el nombre del archivo y no en la ruta.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Match", "score", "search"]

# Puntos por cada clase de acierto. Los numeros salen de probar con rutas
# reales: sin el premio a lo consecutivo, `app` encontraba antes
# `a/p/p.py` que `app.py`.
_PUNTO_BASE = 1
_PREMIO_CONSECUTIVO = 8
_PREMIO_INICIO_PALABRA = 6
_PREMIO_INICIO = 10
_CASTIGO_HUECO = 1
_PREMIO_NOMBRE = 15

_SEPARADORES = "/_-. "


@dataclass(frozen=True)
class Match:
    text: str
    score: int
    positions: tuple[int, ...]


def score(needle: str, haystack: str) -> tuple[int, tuple[int, ...]] | None:
    """Puntuar una candidata. `None` si no contiene las letras en orden."""
    if not needle:
        return 0, ()
    aguja = needle.lower()
    pajar = haystack.lower()

    puntos = 0
    posiciones: list[int] = []
    indice = 0
    anterior = -2

    for letra in aguja:
        encontrado = pajar.find(letra, indice)
        if encontrado == -1:
            return None

        puntos += _PUNTO_BASE
        if encontrado == anterior + 1:
            puntos += _PREMIO_CONSECUTIVO
        elif encontrado == 0:
            puntos += _PREMIO_INICIO
        elif pajar[encontrado - 1] in _SEPARADORES:
            puntos += _PREMIO_INICIO_PALABRA
        else:
            # Cuanto mas lejos cae la letra, peor: evita que una coincidencia
            # desperdigada por toda la ruta gane a una compacta.
            puntos -= min(_CASTIGO_HUECO * (encontrado - anterior - 1), 10)

        posiciones.append(encontrado)
        anterior = encontrado
        indice = encontrado + 1

    # Lo que cae en el nombre del archivo vale mas que lo que cae en la ruta:
    # quien escribe «session» busca session.py, no la carpeta sessions/.
    corte = haystack.rfind("/") + 1
    en_nombre = sum(1 for p in posiciones if p >= corte)
    puntos += en_nombre * _PREMIO_NOMBRE

    # Entre dos aciertos iguales, gana la ruta mas corta.
    puntos -= len(haystack) // 20
    return puntos, tuple(posiciones)


def search(needle: str, candidates: list[str], limit: int = 30) -> list[Match]:
    """Las mejores candidatas, de mas a menos parecida."""
    if not needle.strip():
        return [Match(c, 0, ()) for c in candidates[:limit]]

    resultados: list[Match] = []
    for candidata in candidates:
        puntuada = score(needle, candidata)
        if puntuada is not None:
            resultados.append(Match(candidata, puntuada[0], puntuada[1]))

    resultados.sort(key=lambda m: (-m.score, len(m.text), m.text))
    return resultados[:limit]


def highlight(match: Match, on: str = "reverse") -> str:
    """La candidata con las letras que han encajado resaltadas."""
    if not match.positions:
        return match.text
    piezas: list[str] = []
    ultimo = 0
    for posicion in match.positions:
        piezas.append(match.text[ultimo:posicion])
        piezas.append(f"[{on}]{match.text[posicion]}[/]")
        ultimo = posicion + 1
    piezas.append(match.text[ultimo:])
    return "".join(piezas)
