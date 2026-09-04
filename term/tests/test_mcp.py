"""Tests del cliente MCP, contra un servidor de mentira que habla el protocolo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from term.mcp import (
    McpClient,
    McpRegistry,
    McpServer,
    McpTool,
    load_servers,
    sanitize_name,
    save_servers,
)

SERVIDOR = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


def servidor_falso(nombre: str = "falso") -> McpServer:
    return McpServer(name=nombre, command=sys.executable, args=[SERVIDOR])


class TestNombres:
    def test_se_limpian_para_que_las_apis_los_acepten(self):
        """Los tres formatos exigen [A-Za-z0-9_-] en el nombre de función."""
        assert sanitize_name("mi servidor.raro") == "mi_servidor_raro"
        assert sanitize_name("github") == "github"
        assert sanitize_name("!!!") == "mcp"

    def test_el_nombre_lleva_el_servidor_por_delante(self):
        """Dos servidores pueden publicar una herramienta con el mismo nombre."""
        uno = McpTool(server="github", name="search")
        otro = McpTool(server="gitlab", name="search")
        assert uno.qualified != otro.qualified
        assert uno.qualified == "mcp_github_search"


class TestConfiguracion:
    def test_lee_el_formato_estandar(self, tmp_path):
        """Se usa el mismo mcpServers que el resto, para poder copiar y pegar."""
        ruta = tmp_path / "mcp.json"
        ruta.write_text(json.dumps({"mcpServers": {
            "github": {"command": "npx", "args": ["-y", "server-github"],
                       "env": {"TOKEN": "x"}},
        }}))
        servidores = load_servers(ruta)
        assert len(servidores) == 1
        assert servidores[0].name == "github"
        assert servidores[0].args == ["-y", "server-github"]
        assert servidores[0].env == {"TOKEN": "x"}

    def test_una_entrada_sin_comando_se_salta(self, tmp_path):
        ruta = tmp_path / "mcp.json"
        ruta.write_text(json.dumps({"mcpServers": {
            "malo": {"args": ["x"]}, "bueno": {"command": "echo"},
        }}))
        assert [s.name for s in load_servers(ruta)] == ["bueno"]

    def test_archivo_ausente_o_roto(self, tmp_path):
        assert load_servers(tmp_path / "no-existe.json") == []
        roto = tmp_path / "roto.json"
        roto.write_text("no soy json")
        assert load_servers(roto) == []

    def test_ida_y_vuelta(self, tmp_path):
        ruta = tmp_path / "mcp.json"
        original = [McpServer(name="uno", command="npx", args=["-y", "algo"])]
        assert save_servers(original, ruta)
        assert load_servers(ruta)[0].args == ["-y", "algo"]

    def test_un_servidor_desactivado_se_recuerda(self, tmp_path):
        ruta = tmp_path / "mcp.json"
        save_servers([McpServer(name="off", command="echo", enabled=False)], ruta)
        assert load_servers(ruta)[0].enabled is False


class TestCliente:
    async def test_arranca_y_descubre_las_herramientas(self):
        client = McpClient(servidor_falso())
        assert await client.start(), client.error
        try:
            assert {t.name for t in client.tools} == {"saludar", "sumar"}
            herramienta = next(t for t in client.tools if t.name == "sumar")
            assert herramienta.schema["required"] == ["a", "b"]
        finally:
            await client.stop()

    async def test_se_salta_lo_que_no_es_json(self):
        """Algunos servidores escriben avisos sueltos por stdout."""
        client = McpClient(servidor_falso())
        assert await client.start(), client.error
        await client.stop()

    async def test_llama_a_una_herramienta(self):
        client = McpClient(servidor_falso())
        await client.start()
        try:
            ok, salida = await client.call("saludar", {"nombre": "Term"})
            assert ok and salida == "Hola, Term"
            ok, salida = await client.call("sumar", {"a": 20, "b": 22})
            assert ok and salida == "42"
        finally:
            await client.stop()

    async def test_un_error_del_servidor_no_revienta(self):
        client = McpClient(servidor_falso())
        await client.start()
        try:
            ok, salida = await client.call("noexiste", {})
            assert not ok
            assert "noexiste" in salida
        finally:
            await client.stop()

    async def test_un_binario_que_no_existe(self):
        client = McpClient(McpServer(name="fantasma", command="no-existe-este-binario"))
        assert not await client.start()
        assert "no se encuentra" in client.error

    async def test_parar_es_idempotente(self):
        client = McpClient(servidor_falso())
        await client.start()
        await client.stop()
        await client.stop()
        assert not client.running


class TestRegistro:
    async def test_junta_las_herramientas_de_varios_servidores(self):
        registro = McpRegistry([servidor_falso("uno"), servidor_falso("dos")])
        fallos = await registro.start_all()
        try:
            assert fallos == {}
            assert len(registro.tools()) == 4
            nombres = {t.qualified for t in registro.tools()}
            assert "mcp_uno_saludar" in nombres
            assert "mcp_dos_saludar" in nombres
        finally:
            await registro.stop_all()

    async def test_no_arranca_los_desactivados(self):
        apagado = servidor_falso("apagado")
        apagado.enabled = False
        registro = McpRegistry([apagado])
        await registro.start_all()
        try:
            assert registro.tools() == []
        finally:
            await registro.stop_all()

    async def test_un_servidor_roto_no_impide_los_demas(self):
        registro = McpRegistry([
            McpServer(name="roto", command="no-existe-este-binario"),
            servidor_falso("bueno"),
        ])
        fallos = await registro.start_all()
        try:
            assert "roto" in fallos
            assert len(registro.tools()) == 2
        finally:
            await registro.stop_all()

    async def test_llamar_por_el_nombre_cualificado(self):
        registro = McpRegistry([servidor_falso("uno")])
        await registro.start_all()
        try:
            ok, salida = await registro.call("mcp_uno_saludar", {"nombre": "x"})
            assert ok and "Hola, x" in salida
            ok, salida = await registro.call("mcp_uno_nada", {})
            assert not ok
        finally:
            await registro.stop_all()

    async def test_stop_all_no_deja_procesos(self):
        registro = McpRegistry([servidor_falso()])
        await registro.start_all()
        clientes = list(registro.clients.values())
        await registro.stop_all()
        assert all(not c.running for c in clientes)
        assert registro.clients == {}


class TestIntegracionConLasHerramientas:
    async def test_se_ofrecen_junto_a_las_nativas(self):
        from term.tools import TOOLS, ToolContext, available_tools

        registro = McpRegistry([servidor_falso()])
        await registro.start_all()
        try:
            ctx = ToolContext(mcp=registro)
            nombres = {t.name for t in available_tools(ctx)}
            assert len(nombres) == len(TOOLS) + 2
            assert "mcp_falso_saludar" in nombres
        finally:
            await registro.stop_all()

    async def test_van_en_los_tres_formatos_de_esquema(self):
        from term.tools import (
            ToolContext,
            schemas_anthropic,
            schemas_gemini,
            schemas_openai,
        )

        registro = McpRegistry([servidor_falso()])
        await registro.start_all()
        try:
            ctx = ToolContext(mcp=registro)
            openai = {e["function"]["name"] for e in schemas_openai(ctx)}
            anthropic = {e["name"] for e in schemas_anthropic(ctx)}
            gemini = {f["name"]
                      for f in schemas_gemini(ctx)[0]["function_declarations"]}
            assert "mcp_falso_saludar" in openai == anthropic == gemini
        finally:
            await registro.stop_all()

    async def test_se_ejecutan_por_el_mismo_camino(self):
        from term.tools import ToolContext, execute_async

        registro = McpRegistry([servidor_falso()])
        await registro.start_all()
        try:
            ctx = ToolContext(mcp=registro)
            ok, salida = await execute_async(
                "mcp_falso_saludar", {"nombre": "Term"}, ctx)
            assert ok and "Hola, Term" in salida
        finally:
            await registro.stop_all()

    async def test_sin_permisos_de_sistema_no_se_ofrecen(self):
        """Un servidor externo puede hacer cualquier cosa: cuenta como sistema."""
        from term.tools import ToolContext, available_tools

        registro = McpRegistry([servidor_falso()])
        await registro.start_all()
        try:
            ctx = ToolContext(mcp=registro, allow_system=False)
            assert not any(t.name.startswith("mcp_") for t in available_tools(ctx))
            ok, motivo = await __import__(
                "term.tools", fromlist=["x"]).execute_async(
                    "mcp_falso_saludar", {}, ctx)
            assert not ok and "permisos" in motivo
        finally:
            await registro.stop_all()

    async def test_sin_registro_no_hay_herramientas_mcp(self):
        from term.tools import ToolContext, mcp_tools

        assert mcp_tools(ToolContext()) == []
