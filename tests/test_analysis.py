"""Testes da Etapa 3 — narrativa determinística."""

from __future__ import annotations

import datetime as dt
import math

from pim_report.analysis import formatar_pct, gerar_narrativa
from pim_report.transform import construir_dados


def test_formatar_pct_padrao_brasileiro():
    assert formatar_pct(1.23) == "+1,2%"
    assert formatar_pct(-4.0) == "-4,0%"
    assert formatar_pct(math.nan) == "n/d"


def test_manchete_e_subtitulo(pacote_exemplo):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    narrativa = gerar_narrativa(dados)
    # mensal +0,7 -> "avançou"; mês de referência presente
    assert "avançou" in narrativa.manchete
    assert "abril 2026" in narrativa.manchete
    # subtítulo traz as outras leituras
    assert "-1,5%" in narrativa.subtitulo
    assert "Em 12 meses" in narrativa.subtitulo


def test_contexto_relaciona_mensal_e_tendencia(pacote_exemplo):
    # mensal +0,7 (alta) com 12 meses -1,0 (queda) -> deve mencionar contraste
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    narrativa = gerar_narrativa(dados)
    assert "contrasta" in narrativa.paragrafo_contexto
    assert "pontos" in narrativa.paragrafo_contexto


def test_destaques_aparecem_na_narrativa(pacote_exemplo):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    narrativa = gerar_narrativa(dados)
    assert "alimentícios" in narrativa.texto_altas
    assert "têxteis" in narrativa.texto_baixas
