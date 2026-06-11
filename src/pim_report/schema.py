"""schema.py — validação do DataFrame cru com pandera (falha cedo e clara).

Se o IBGE mudar colunas/tipos do layout SIDRA, a esteira deve falhar imediatamente com uma
mensagem clara — e não produzir uma nota silenciosamente errada. Toda falha de validação vira
:class:`~pim_report.exceptions.SchemaValidationError` (Martin: princípios 1 e 4), com o relatório
de erros do pandera anexado ao contexto e encadeado via ``raise ... from``.
"""

from __future__ import annotations

import pandas as pd

try:  # pandera >= 0.20 recomenda o namespace .pandas
    import pandera.pandas as pa
except ImportError:  # pragma: no cover - compatibilidade
    import pandera as pa

from .exceptions import SchemaValidationError, exigir_nao_nulo

# Colunas mínimas que a esteira consome do retorno do SIDRA.
# (D2C=variável, D3C=período, D4C=classificação/categoria, V=valor, NN=nível territorial)
COLUNAS_OBRIGATORIAS: tuple[str, ...] = ("NN", "V", "D2C", "D2N", "D3C", "D3N", "D4C", "D4N")

SCHEMA_BRUTO = pa.DataFrameSchema(
    {
        "NN": pa.Column(str, nullable=False),
        "V": pa.Column(str, nullable=True),  # "..." e "-" aparecem; coerção numérica é no transform
        "D2C": pa.Column(str, nullable=False),
        "D2N": pa.Column(str, nullable=False),
        "D3C": pa.Column(str, nullable=False),
        "D3N": pa.Column(str, nullable=False),
        "D4C": pa.Column(str, nullable=False),
        "D4N": pa.Column(str, nullable=False),
    },
    strict=False,  # tolera colunas extras do SIDRA (NC, MC, D1C, ...)
    coerce=True,
    name="PIM-PF (SIDRA cru)",
)


def validar_bruto(df: pd.DataFrame) -> pd.DataFrame:
    """Valida o DataFrame cru (já sem a linha de cabeçalho) contra :data:`SCHEMA_BRUTO`.

    Returns:
        O DataFrame validado (e com tipos coeridos).

    Raises:
        SchemaValidationError: se faltarem colunas ou os tipos não baterem.
    """
    exigir_nao_nulo(df, "df", operacao="validar_bruto")

    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltantes:
        raise SchemaValidationError(
            "Layout do SIDRA mudou: colunas obrigatórias ausentes",
            contexto={"colunas_ausentes": faltantes, "colunas_recebidas": list(df.columns)},
        )

    try:
        return SCHEMA_BRUTO.validate(df, lazy=True)
    except pa.errors.SchemaErrors as erro:
        raise SchemaValidationError(
            "DataFrame cru não passou na validação de schema (pandera)",
            contexto={"falhas": str(erro.failure_cases.to_dict(orient="records")[:10])},
        ) from erro
