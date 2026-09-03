from __future__ import annotations

from term.models import (
    DEFAULT_MODEL_REF,
    EFFORT_LEVELS,
    catalog,
    model_label,
    normalise_ref,
    provider_label,
)


class TestReferencias:
    def test_vacio_da_el_modelo_por_defecto(self):
        assert normalise_ref("") == DEFAULT_MODEL_REF
        assert normalise_ref("   ") == DEFAULT_MODEL_REF

    def test_referencias_de_versiones_anteriores(self):
        """Una config vieja guardaba 'opus' a secas, sin proveedor."""
        assert normalise_ref("opus") == "claude/opus"
        assert normalise_ref("claude-haiku") == "claude/haiku"
        assert normalise_ref("claude") == "claude/default"

    def test_referencia_completa_se_respeta(self):
        assert normalise_ref("opencode/gpt-5.2") == "opencode/gpt-5.2"
        assert normalise_ref("ollama/llama3.3") == "ollama/llama3.3"

    def test_el_modelo_de_opencode_conserva_su_casa(self):
        """opencode nombra sus modelos como casa/modelo; la segunda barra
        forma parte del modelo, no del proveedor."""
        assert normalise_ref("opencode/anthropic/claude-opus-4-5") == (
            "opencode/anthropic/claude-opus-4-5")

    def test_un_proveedor_desconocido_se_trata_como_modelo_de_claude(self):
        assert normalise_ref("inventado/x").startswith("claude/")


class TestEtiquetas:
    def test_el_modelo_por_defecto_se_llama_claude_a_secas(self):
        """La barra de estado es estrecha: no cabe 'Claude Code · default'."""
        assert model_label("claude/default") == "Claude"

    def test_incluye_proveedor_y_modelo(self):
        etiqueta = model_label("opencode/gpt-5.2")
        assert "opencode" in etiqueta
        assert "gpt-5.2" in etiqueta

    def test_recorta_la_casa_del_modelo(self):
        etiqueta = model_label("opencode/anthropic/claude-opus-4-5")
        assert "claude-opus-4-5" in etiqueta
        assert "anthropic/" not in etiqueta

    def test_etiqueta_de_proveedor(self):
        assert provider_label("opencode/gpt-5.2") == "opencode"
        assert provider_label("claude/opus") == "Claude Code"


class TestCatalogo:
    def test_solo_ofrece_proveedores_instalados(self):
        """Proponer un modelo que no se puede ejecutar solo da un error luego."""
        from term.providers import get_provider

        for ref, _, _ in catalog(only_installed=True):
            provider_key = ref.split("/")[0]
            assert get_provider(provider_key).available()

    def test_sin_filtrar_incluye_todos(self):
        assert len(catalog(only_installed=False)) >= len(catalog(True))

    def test_las_referencias_del_catalogo_son_validas(self):
        for ref, etiqueta, proveedor in catalog(only_installed=False):
            assert normalise_ref(ref) == ref
            assert etiqueta and proveedor


def test_los_niveles_de_esfuerzo_van_de_menos_a_mas():
    assert EFFORT_LEVELS == ["low", "medium", "high", "max"]
