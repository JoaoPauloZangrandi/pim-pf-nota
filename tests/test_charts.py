"""Testes da Etapa 4 — gráficos (gera PDF e PNG não vazios)."""

from __future__ import annotations

import datetime as dt

from pim_report.charts import gerar_graficos
from pim_report.transform import construir_dados


def test_gera_pdf_e_png(pacote_exemplo, tmp_path):
    dados = construir_dados(pacote_exemplo, data_extracao=dt.date(2026, 6, 11))
    graficos = gerar_graficos(dados, dir_saida=tmp_path)
    for caminho in (
        graficos.serie_pdf,
        graficos.serie_png,
        graficos.categorias_pdf,
        graficos.categorias_png,
    ):
        assert caminho.exists()
        assert caminho.stat().st_size > 0
