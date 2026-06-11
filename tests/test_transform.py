"""Testes da Etapa 3 — transformação: 4 leituras, categorias, seções e destaques."""

from __future__ import annotations

import datetime as dt
import math

import pytest

from pim_report import config
from pim_report.exceptions import TransformError
from pim_report.special_cases import ResultadoPeriodo
from pim_report.transform import _para_float, construir_dados


def test_para_float_trata_ausentes_como_nan():
    assert _para_float("1,2") == 1.2
    assert _para_float("3.4") == 3.4
    assert math.isnan(_para_float("..."))
    assert math.isnan(_para_float("-"))
    assert math.isnan(_para_float(None))


def test_constroi_dados_do_pacote(pacote_exemplo):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    assert dados.publicado is True
    assert isinstance(dados, ResultadoPeriodo)
    assert dados.periodo == "202604"
    assert dados.periodo_nome == "abril 2026"
    assert dados.industria_geral.var_mensal == 0.7
    assert dados.industria_geral.var_interanual == -1.5
    assert dados.indice_dessaz == 98.5


def test_quatro_leituras_da_industria_geral(pacote_exemplo):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    leituras = dados.leituras
    assert len(leituras) == 4
    assert set(leituras) == set(config.LEITURAS)
    assert leituras["Acumulado em 12 meses"] == -1.0


def test_secoes_e_categorias_economicas(pacote_exemplo):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    nomes_secoes = {s.nome for s in dados.secoes}
    assert "Indústrias extrativas" in nomes_secoes
    assert "Indústrias de transformação" in nomes_secoes
    assert len(dados.categorias_economicas) == 4


def test_destaques_pegam_maior_alta_e_maior_baixa(pacote_exemplo):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    assert dados.maiores_altas[0].nome == "Fabricação de produtos alimentícios"  # +5,0
    assert dados.maiores_baixas[0].nome == "Fabricação de produtos têxteis"  # -8,0


def test_serie_dessaz_ordenada(pacote_exemplo):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    assert len(dados.serie_indice) == 3
    periodos = [p for p, _ in dados.serie_indice]
    assert periodos == sorted(periodos)
    assert dados.serie_indice[-1] == ("202604", 98.5)


def test_pacote_incompleto_falha(pacote_exemplo):
    del pacote_exemplo["serie"]
    with pytest.raises(TransformError):
        construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
