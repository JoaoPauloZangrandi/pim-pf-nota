"""Testes da Etapa 2 — validação de schema (pandera)."""

from __future__ import annotations

import pandas as pd
import pytest

from pim_report.exceptions import InvalidParameterError, SchemaValidationError
from pim_report.schema import validar_bruto


def _df_valido() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "NN": "Brasil",
                "V": "1.2",
                "D2C": "11601",
                "D2N": "Variação mensal",
                "D3C": "202604",
                "D3N": "abril 2026",
                "D4C": "129314",
                "D4N": "1 Indústria geral",
                "NC": "1",  # coluna extra tolerada
            }
        ]
    )


def test_dataframe_valido_passa():
    validado = validar_bruto(_df_valido())
    assert len(validado) == 1


def test_coluna_ausente_falha_cedo_e_claro():
    df = _df_valido().drop(columns=["D4C"])
    with pytest.raises(SchemaValidationError) as info:
        validar_bruto(df)
    assert "D4C" in str(info.value)


def test_none_e_rejeitado():
    with pytest.raises(InvalidParameterError):
        validar_bruto(None)
