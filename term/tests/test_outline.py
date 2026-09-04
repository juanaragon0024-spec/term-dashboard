"""Tests del esqueleto de código."""

from __future__ import annotations

from term.outline import build_outline, extract, outline_file


class TestPython:
    def test_funcion_con_firma_completa(self, tmp_path):
        archivo = tmp_path / "m.py"
        archivo.write_text(
            "def sumar(a: int, b: int = 2, *, exacto: bool = True) -> float:\n"
            '    """Suma dos números."""\n'
            "    return a + b\n")
        simbolo = extract(archivo)[0]
        assert simbolo.kind == "funcion"
        assert simbolo.signature == (
            "def sumar(a: int, b: int = 2, *, exacto: bool = True) -> float")
        assert simbolo.doc == "Suma dos números."

    def test_clase_con_sus_metodos(self, tmp_path):
        archivo = tmp_path / "m.py"
        archivo.write_text(
            "class Motor(Base):\n"
            "    def arrancar(self) -> None: ...\n"
            "    async def parar(self): ...\n")
        tipos = [(s.kind, s.name) for s in extract(archivo)]
        assert tipos == [("clase", "Motor"), ("metodo", "arrancar"),
                         ("metodo", "parar")]
        assert "class Motor(Base)" in extract(archivo)[0].signature

    def test_async_se_marca(self, tmp_path):
        archivo = tmp_path / "m.py"
        archivo.write_text("async def traer(url: str) -> bytes: ...\n")
        assert extract(archivo)[0].signature.startswith("async def")

    def test_lo_privado_no_sale(self, tmp_path):
        """A quien llama desde fuera no le sirve un _helper."""
        archivo = tmp_path / "m.py"
        archivo.write_text("def publica(): ...\ndef _privada(): ...\n")
        assert [s.name for s in extract(archivo)] == ["publica"]

    def test_las_constantes_de_modulo_si(self, tmp_path):
        archivo = tmp_path / "m.py"
        archivo.write_text("TIMEOUT = 30\nminuscula = 1\n")
        assert [s.name for s in extract(archivo)] == ["TIMEOUT"]

    def test_un_archivo_roto_no_revienta(self, tmp_path):
        archivo = tmp_path / "roto.py"
        archivo.write_text("def sin cerrar(:\n")
        assert extract(archivo) == []

    def test_argumentos_variables(self, tmp_path):
        archivo = tmp_path / "m.py"
        archivo.write_text("def f(*args, **kwargs): ...\n")
        assert extract(archivo)[0].signature == "def f(*args, **kwargs)"


class TestOtrosLenguajes:
    def test_javascript(self, tmp_path):
        archivo = tmp_path / "a.js"
        archivo.write_text(
            "export function saludar(nombre) {}\n"
            "const sumar = (a, b) => a + b\n"
            "class Motor {}\n")
        nombres = {s.name for s in extract(archivo)}
        assert {"saludar", "sumar", "Motor"} <= nombres

    def test_typescript_con_interfaces(self, tmp_path):
        archivo = tmp_path / "a.ts"
        archivo.write_text("export interface Usuario { id: string }\n"
                           "export type Rol = 'admin' | 'user'\n")
        nombres = {s.name for s in extract(archivo)}
        assert {"Usuario", "Rol"} <= nombres

    def test_go(self, tmp_path):
        archivo = tmp_path / "a.go"
        archivo.write_text("type Servidor struct {}\n"
                           "func Arrancar(puerto int) error {\n}\n")
        nombres = {s.name for s in extract(archivo)}
        assert {"Servidor", "Arrancar"} <= nombres

    def test_rust(self, tmp_path):
        archivo = tmp_path / "a.rs"
        archivo.write_text("pub struct Motor {}\npub fn arrancar() {}\n")
        nombres = {s.name for s in extract(archivo)}
        assert {"Motor", "arrancar"} <= nombres

    def test_una_extension_desconocida_no_da_nada(self, tmp_path):
        archivo = tmp_path / "a.xyz"
        archivo.write_text("lo que sea")
        assert extract(archivo) == []


class TestFachada:
    def test_outline_de_un_archivo(self, tmp_path):
        archivo = tmp_path / "m.py"
        archivo.write_text("def hola() -> str: ...\n")
        texto = outline_file(archivo)
        assert str(archivo) in texto
        assert "def hola() -> str" in texto

    def test_un_archivo_vacio_no_produce_nada(self, tmp_path):
        archivo = tmp_path / "vacio.py"
        archivo.write_text("")
        assert outline_file(archivo) == ""

    def test_el_presupuesto_se_respeta(self, tmp_path):
        """Va dentro del prompt de cada turno: sin tope costaría más que los
        archivos que pretende ahorrar."""
        archivos = []
        for i in range(30):
            archivo = tmp_path / f"m{i}.py"
            archivo.write_text("".join(
                f"def funcion_numero_{j}(argumento: str) -> str: ...\n"
                for j in range(40)))
            archivos.append(archivo)
        texto = build_outline(archivos, budget=2_000)
        assert len(texto) < 4_000
        assert "archivos más" in texto

    def test_un_archivo_enorme_se_salta(self, tmp_path):
        archivo = tmp_path / "gigante.py"
        archivo.write_text("x = 1\n" * 200_000)
        assert extract(archivo) == []

    def test_un_archivo_que_no_existe(self, tmp_path):
        assert extract(tmp_path / "fantasma.py") == []
