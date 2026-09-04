"""Tests de los procesos en segundo plano."""

from __future__ import annotations

import asyncio

import pytest

from term.jobs import JobManager, looks_long_running


@pytest.fixture
async def manager():
    jm = JobManager()
    yield jm
    await jm.stop_all()


class TestArrancar:
    async def test_devuelve_enseguida_sin_esperar(self, manager, tmp_path):
        """Lo contrario es lo que obliga a abrir otra terminal."""
        import time

        empezado = time.monotonic()
        job = await manager.start("sleep 5", str(tmp_path))
        assert time.monotonic() - empezado < 1
        assert job.running

    async def test_recoge_la_salida(self, manager, tmp_path):
        job = await manager.start("echo uno; echo dos", str(tmp_path))
        await asyncio.sleep(0.5)
        assert "uno" in job.tail() and "dos" in job.tail()
        assert job.exit_code == 0

    async def test_junta_la_salida_de_error(self, manager, tmp_path):
        """En una terminal las dos salidas se ven mezcladas; aquí igual."""
        job = await manager.start("echo normal; echo malo >&2", str(tmp_path))
        await asyncio.sleep(0.5)
        assert "normal" in job.tail() and "malo" in job.tail()

    async def test_corre_en_el_directorio_indicado(self, manager, tmp_path):
        (tmp_path / "marca.txt").write_text("x")
        job = await manager.start("ls", str(tmp_path))
        await asyncio.sleep(0.5)
        assert "marca.txt" in job.tail()

    async def test_admite_tuberias_y_comodines(self, manager, tmp_path):
        job = await manager.start("echo hola | tr a-z A-Z", str(tmp_path))
        await asyncio.sleep(0.5)
        assert "HOLA" in job.tail()

    async def test_un_comando_que_no_existe_se_registra(self, manager, tmp_path):
        job = await manager.start("comando-que-no-existe-jamas", str(tmp_path))
        await asyncio.sleep(0.5)
        assert not job.running
        assert job.exit_code != 0

    async def test_cada_proceso_tiene_su_numero(self, manager, tmp_path):
        uno = await manager.start("echo a", str(tmp_path))
        dos = await manager.start("echo b", str(tmp_path))
        assert uno.id != dos.id
        assert manager.latest().id == dos.id


class TestEstado:
    async def test_terminado_frente_a_fallido(self, manager, tmp_path):
        bien = await manager.start("true", str(tmp_path))
        mal = await manager.start("exit 3", str(tmp_path))
        await asyncio.sleep(0.5)
        assert bien.status == "terminado"
        assert "falló" in mal.status and "3" in mal.status

    async def test_parado_a_mano_no_cuenta_como_fallo(self, manager, tmp_path):
        """Un proceso que paras tú no es un error, y la lista debe decirlo."""
        job = await manager.start("sleep 30", str(tmp_path))
        await asyncio.sleep(0.3)
        await manager.stop(job.id)
        assert job.status == "parado"

    async def test_la_duracion_se_lee(self, manager, tmp_path):
        job = await manager.start("echo x", str(tmp_path))
        await asyncio.sleep(0.4)
        assert job.elapsed_label.endswith(("s", "m", "h"))


class TestSalida:
    async def test_el_buffer_esta_acotado(self, manager, tmp_path):
        """Un servidor lleva horas escribiendo: sin tope se come la memoria."""
        from term.jobs import _MAX_LINES

        job = await manager.start(f"seq 1 {_MAX_LINES + 500}", str(tmp_path))
        await asyncio.sleep(2)
        assert len(job.lines) <= _MAX_LINES
        # Se conserva el final, que es lo que interesa.
        assert str(_MAX_LINES + 500) in job.tail()

    async def test_buscar_dentro_de_la_salida(self, manager, tmp_path):
        job = await manager.start(
            "echo normal; echo 'ERROR: puerto ocupado'; echo otra", str(tmp_path))
        await asyncio.sleep(0.5)
        assert "puerto ocupado" in job.search("error")
        assert job.search("no aparece") == ""

    async def test_sin_salida_todavia(self, manager, tmp_path):
        job = await manager.start("sleep 5", str(tmp_path))
        assert "sin salida" in job.tail()


class TestParar:
    async def test_para_el_proceso(self, manager, tmp_path):
        job = await manager.start("sleep 30", str(tmp_path))
        await asyncio.sleep(0.3)
        assert await manager.stop(job.id)
        assert not job.running

    async def test_parar_uno_que_ya_terminó(self, manager, tmp_path):
        job = await manager.start("true", str(tmp_path))
        await asyncio.sleep(0.5)
        assert not await manager.stop(job.id)

    async def test_parar_uno_que_no_existe(self, manager):
        assert not await manager.stop(999)

    async def test_para_tambien_a_los_hijos(self, manager, tmp_path):
        """Un `npm run dev` deja el servidor vivo si solo matas al padre."""
        marca = tmp_path / "sigue-vivo.txt"
        job = await manager.start(
            f"sh -c 'sleep 30 && touch {marca}' & wait", str(tmp_path))
        await asyncio.sleep(0.4)
        await manager.stop(job.id)
        await asyncio.sleep(0.4)
        assert not marca.exists()

    async def test_stop_all(self, manager, tmp_path):
        for _ in range(3):
            await manager.start("sleep 30", str(tmp_path))
        assert await manager.stop_all() == 3
        assert manager.running() == []


class TestParaLaIa:
    async def test_resumen_sin_procesos(self, manager):
        assert "No hay" in manager.summary_for_ai()

    async def test_resumen_con_procesos(self, manager, tmp_path):
        await manager.start("echo hola", str(tmp_path))
        await asyncio.sleep(0.4)
        resumen = manager.summary_for_ai()
        assert "echo hola" in resumen and "[1]" in resumen

    async def test_logs_del_ultimo_por_defecto(self, manager, tmp_path):
        await manager.start("echo primero", str(tmp_path))
        await manager.start("echo segundo", str(tmp_path))
        await asyncio.sleep(0.5)
        assert "segundo" in manager.logs_for_ai()

    async def test_logs_filtrados(self, manager, tmp_path):
        await manager.start("sh script.sh", str(tmp_path))
        job = manager.latest()
        job.lines.extend(["arranque correcto", "FALLO grave", "otra línea"])
        # La cabecera repite el comando, así que se mira solo el cuerpo.
        cuerpo = manager.logs_for_ai(grep="fallo").split("\n\n", 1)[1]
        assert "FALLO grave" in cuerpo
        assert "arranque correcto" not in cuerpo

    async def test_logs_de_un_numero_que_no_existe(self, manager):
        assert "ningún proceso" in manager.logs_for_ai(99)


class TestDeteccionDeServidores:
    @pytest.mark.parametrize("cmd", [
        "npm run dev", "yarn dev", "python manage.py runserver",
        "uvicorn app:main --reload", "pytest --watch", "tail -f log.txt",
        "docker compose up",
    ])
    def test_reconoce_los_que_no_terminan(self, cmd):
        assert looks_long_running(cmd)

    @pytest.mark.parametrize("cmd", ["ls -la", "git status", "echo hola", "pytest"])
    def test_no_confunde_los_que_si_terminan(self, cmd):
        assert not looks_long_running(cmd)

    def test_un_comando_con_comillas_sin_cerrar_no_revienta(self):
        assert looks_long_running('echo "sin cerrar') in (True, False)
