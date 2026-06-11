"""Fixtures compartilhadas: um pacote cru sintético no formato SIDRA.

Permite testar transform/analysis/charts/render sem tocar a rede.
"""

from __future__ import annotations

import pytest

from pim_report import config

_HEADER = {
    "NC": "Nível Territorial (Código)",
    "NN": "Nível Territorial",
    "MC": "Unidade de Medida (Código)",
    "MN": "Unidade de Medida",
    "V": "Valor",
    "D1C": "Brasil (Código)",
    "D1N": "Brasil",
    "D2C": "Variável (Código)",
    "D2N": "Variável",
    "D3C": "Mês (Código)",
    "D3N": "Mês",
    "D4C": "Classificação (Código)",
    "D4N": "Classificação",
}


def _rec(valor, *, d2c, d3c, d3n, d4c, d4n):
    return {
        "NC": "1",
        "NN": "Brasil",
        "MC": "2",
        "MN": "%",
        "V": valor,
        "D1C": "1",
        "D1N": "Brasil",
        "D2C": d2c,
        "D2N": "Variável",
        "D3C": d3c,
        "D3N": d3n,
        "D4C": d4c,
        "D4N": d4n,
    }


# Leituras (var_mensal, interanual, acum_ano, acum_12m, indice_dessaz) por categoria.
_ATIV = {
    config.CAT_INDUSTRIA_GERAL: ("1 Indústria geral", ["0.7", "-1.5", "-0.8", "-1.0", "98.5"]),
    config.CAT_EXTRATIVA: ("2 Indústrias extrativas", ["1.1", "2.0", "1.5", "1.8", "101.2"]),
    config.CAT_TRANSFORMACAO: (
        "3 Indústrias de transformação",
        ["0.5", "-2.1", "-1.2", "-1.4", "97.9"],
    ),
    "129317": ("3.10 Fabricação de produtos alimentícios", ["0.9", "5.0", "3.2", "4.1", "104.0"]),
    "129318": ("3.11 Fabricação de bebidas", ["0.2", "3.0", "1.0", "0.8", "100.5"]),
    "129320": ("3.13 Fabricação de produtos têxteis", ["-1.2", "-8.0", "-5.0", "-6.0", "90.0"]),
    "129321": ("3.14 Confecção de artigos do vestuário", ["-0.4", "-4.0", "-2.0", "-3.0", "94.0"]),
}

_VARS = [
    config.VAR_VAR_MENSAL,
    config.VAR_INTERANUAL,
    config.VAR_ACUM_ANO,
    config.VAR_ACUM_12M,
    config.VAR_INDICE_DESSAZ,
]


@pytest.fixture
def pacote_exemplo() -> dict:
    # 8888 — último período, todas as categorias, 5 variáveis
    atividades = [_HEADER]
    for d4c, (d4n, valores) in _ATIV.items():
        for var, val in zip(_VARS, valores, strict=True):
            atividades.append(_rec(val, d2c=var, d3c="202604", d3n="abril 2026", d4c=d4c, d4n=d4n))

    # 8888 — série do índice dessazonalizado da indústria geral (3 meses)
    serie = [_HEADER]
    for d3c, d3n, val in [
        ("202602", "fevereiro 2026", "97.8"),
        ("202603", "março 2026", "97.9"),
        ("202604", "abril 2026", "98.5"),
    ]:
        serie.append(
            _rec(
                val,
                d2c=config.VAR_INDICE_DESSAZ,
                d3c=d3c,
                d3n=d3n,
                d4c=config.CAT_INDUSTRIA_GERAL,
                d4n="1 Indústria geral",
            )
        )

    # 8887 — grandes categorias econômicas, 4 leituras
    cats = [_HEADER]
    economicas = {
        config.CAT_BENS_CAPITAL: ("Bens de capital", ["1.5", "3.0", "2.0", "2.5"]),
        config.CAT_BENS_INTERMEDIARIOS: ("Bens intermediários", ["0.3", "-0.5", "-0.2", "-0.4"]),
        config.CAT_CONSUMO_DURAVEIS: ("Bens de consumo duráveis", ["-0.8", "4.0", "3.0", "3.5"]),
        config.CAT_CONSUMO_SEMI_NAO_DURAVEIS: (
            "Bens de consumo semiduráveis e não duráveis",
            ["0.1", "-1.0", "-0.6", "-0.9"],
        ),
    }
    leituras_vars = [
        config.VAR_VAR_MENSAL,
        config.VAR_INTERANUAL,
        config.VAR_ACUM_ANO,
        config.VAR_ACUM_12M,
    ]
    for d4c, (d4n, valores) in economicas.items():
        for var, val in zip(leituras_vars, valores, strict=True):
            cats.append(_rec(val, d2c=var, d3c="202604", d3n="abril 2026", d4c=d4c, d4n=d4n))

    return {"atividades": atividades, "serie": serie, "categorias": cats}
