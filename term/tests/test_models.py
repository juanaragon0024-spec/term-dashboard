from __future__ import annotations

from term.models import AI_MODELS, EFFORT_LEVELS, model_label, resolve_model


def test_el_modelo_predeterminado_no_fuerza_ningun_alias():
    """Sin --model, la CLI usa el modelo que el usuario ya tenga configurado."""
    assert resolve_model("default") == ("default", None)
    assert resolve_model("") == ("default", None)


def test_alias_conocidos():
    assert resolve_model("opus") == ("opus", "opus")
    assert resolve_model("sonnet") == ("sonnet", "sonnet")


def test_claves_de_versiones_anteriores_siguen_funcionando():
    """Una config vieja decia claude-opus; no debe quedar en un modelo invalido."""
    assert resolve_model("claude-opus") == ("opus", "opus")
    assert resolve_model("claude") == ("default", None)


def test_un_identificador_literal_se_pasa_tal_cual():
    key, alias = resolve_model("claude-opus-4-5-20251101")
    assert key == alias == "claude-opus-4-5-20251101"


def test_etiquetas_legibles():
    assert model_label("opus") == AI_MODELS["opus"]["name"]
    assert model_label("un-modelo-raro") == "un-modelo-raro"


def test_los_niveles_de_esfuerzo_estan_ordenados_de_menos_a_mas():
    assert EFFORT_LEVELS == ["low", "medium", "high", "max"]
