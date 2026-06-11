"""Testes da Etapa 0 — hierarquia de exceções + Special Cases.

Estes testes exercitam código JÁ implementado nesta etapa (exceptions.py, special_cases.py),
portanto devem ficar VERDES. Os testes que forçam erros em módulos ainda não implementados
(sidra_client, render) ficam vermelhos — ver test_sidra_client.py e test_render.py.
"""

from __future__ import annotations

import datetime as dt

import pytest

from pim_report import exceptions as ex
from pim_report.exceptions import (
    InvalidParameterError,
    PimReportError,
    SidraHTTPError,
    exigir_nao_nulo,
)
from pim_report.special_cases import PeriodoNaoPublicado, ResultadoPeriodo


# --------------------------------------------------------------------------- #
# Hierarquia de exceções (Martin, princípios 3 e 5)
# --------------------------------------------------------------------------- #
def test_toda_excecao_de_dominio_descende_da_raiz():
    for nome in (
        "SidraError",
        "SidraConnectionError",
        "SidraHTTPError",
        "SidraPayloadError",
        "SidraEmptyError",
        "SchemaValidationError",
        "TransformError",
        "AnalysisError",
        "CacheError",
        "CacheVazioError",
        "RenderError",
        "LatexCompilationError",
        "HtmlRenderError",
        "InvalidParameterError",
    ):
        classe = getattr(ex, nome)
        assert issubclass(classe, PimReportError), f"{nome} deve descender de PimReportError"


def test_familia_sidra_e_render_sao_subarvores_coerentes():
    assert issubclass(ex.SidraConnectionError, ex.SidraError)
    assert issubclass(ex.SidraHTTPError, ex.SidraError)
    assert issubclass(ex.LatexCompilationError, ex.RenderError)
    assert issubclass(ex.CacheVazioError, ex.CacheError)


# --------------------------------------------------------------------------- #
# Contexto nas exceções (Martin, princípio 4)
# --------------------------------------------------------------------------- #
def test_excecao_embute_contexto_na_mensagem():
    erro = PimReportError("falha ao extrair", contexto={"tabela": "8888"})
    assert "falha ao extrair" in str(erro)
    assert "tabela" in str(erro)
    assert "8888" in str(erro)


def test_sidra_http_error_guarda_status_e_classifica_transitorio():
    erro = SidraHTTPError("servidor indisponível", status_code=503)
    assert erro.status_code == 503
    assert erro.transitorio is True
    assert "503" in str(erro)

    erro_cliente = SidraHTTPError("não encontrado", status_code=404)
    assert erro_cliente.transitorio is False


# --------------------------------------------------------------------------- #
# Não passe None (Martin, princípio 8)
# --------------------------------------------------------------------------- #
def test_exigir_nao_nulo_passa_valor_adiante():
    assert exigir_nao_nulo("202504", "periodo") == "202504"


def test_exigir_nao_nulo_rejeita_none_com_contexto():
    with pytest.raises(InvalidParameterError) as info:
        exigir_nao_nulo(None, "periodo", operacao="buscar_tabela")
    assert "periodo" in str(info.value)
    assert info.value.contexto["operacao"] == "buscar_tabela"


# --------------------------------------------------------------------------- #
# Special Case PeriodoNaoPublicado (Martin, princípios 6 e 7)
# --------------------------------------------------------------------------- #
def test_periodo_nao_publicado_nunca_se_diz_publicado():
    snp = PeriodoNaoPublicado("202505", "202504", dt.date(2025, 6, 3))
    assert snp.publicado is False


def test_periodo_nao_publicado_cumpre_a_interface_de_resultado():
    snp = PeriodoNaoPublicado("202505", "202504", dt.date(2025, 6, 3))
    assert isinstance(snp, ResultadoPeriodo)


def test_mensagem_traz_periodos_e_data_para_aviso_acionavel():
    snp = PeriodoNaoPublicado("202505", "202504", dt.date(2025, 6, 3))
    msg = snp.mensagem()
    assert "202505" in msg
    assert "202504" in msg
    assert "03/06/2025" in msg


def test_periodo_nao_publicado_rejeita_campos_none():
    with pytest.raises(InvalidParameterError):
        PeriodoNaoPublicado(None, "202504", dt.date(2025, 6, 3))
    with pytest.raises(InvalidParameterError):
        PeriodoNaoPublicado("202505", None, dt.date(2025, 6, 3))
    with pytest.raises(InvalidParameterError):
        PeriodoNaoPublicado("202505", "202504", None)
