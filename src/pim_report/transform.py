"""transform.py — transforma o pacote cru do SIDRA em estruturas analíticas.

Produz, de forma determinística:
- as 4 leituras padrão da PIM-PF para a indústria geral (manchete + quadro);
- as leituras por grandes categorias econômicas (tabela 8887);
- as seções (extrativa × transformação) e os destaques de atividades (tabela 8888);
- a série do índice dessazonalizado (para o gráfico de nível).

Valores numéricos ausentes no SIDRA ("...", "-") viram ``float('nan')`` — nunca ``None``
(Martin, princípios 1, 7, 8). Qualquer inconsistência estrutural vira :class:`TransformError`.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass
from typing import ClassVar

import pandas as pd

from . import config
from .exceptions import TransformError, exigir_nao_nulo
from .schema import validar_bruto

_PREFIXO_CODIGO = re.compile(r"^[\d.]+\s+")


def _para_float(valor: object) -> float:
    """Converte o campo V do SIDRA para float; ausências viram NaN (não None)."""
    if valor is None:
        return math.nan
    texto = str(valor).strip().replace(",", ".")
    if texto in ("", "-", "..", "...", "…", "X", "x"):
        return math.nan
    try:
        return float(texto)
    except ValueError:
        return math.nan


def _limpar_nome(nome: str) -> str:
    """Remove o prefixo de código CNAE do rótulo: '3.10 Fabricação...' -> 'Fabricação...'."""
    return _PREFIXO_CODIGO.sub("", nome).strip()


@dataclass(frozen=True)
class ItemVariacao:
    """As 4 leituras de uma categoria/atividade num período (valores em %, NaN se ausente)."""

    nome: str
    codigo: str
    var_mensal: float
    var_interanual: float
    acum_ano: float
    acum_12m: float


@dataclass(frozen=True)
class DadosPim:
    """Resultado "feliz" da esteira (contraparte do Special Case PeriodoNaoPublicado).

    Cumpre a interface :class:`~pim_report.special_cases.ResultadoPeriodo` via ``publicado``.
    """

    periodo: str
    periodo_nome: str
    industria_geral: ItemVariacao
    indice_dessaz: float
    secoes: list[ItemVariacao]
    categorias_economicas: list[ItemVariacao]
    maiores_altas: list[ItemVariacao]
    maiores_baixas: list[ItemVariacao]
    serie_indice: list[tuple[str, float]]
    data_extracao: dt.date
    de_cache: bool = False
    data_cache: dt.date | None = None
    fonte: str = config.FONTE
    publicado: ClassVar[bool] = True

    @property
    def leituras(self) -> dict[str, float]:
        """As 4 leituras da indústria geral, no rótulo legível de ``config.LEITURAS``."""
        ig = self.industria_geral
        return {
            "Variação mensal (m/m-1, com ajuste sazonal)": ig.var_mensal,
            "Variação interanual (m/m-12)": ig.var_interanual,
            "Acumulado no ano": ig.acum_ano,
            "Acumulado em 12 meses": ig.acum_12m,
        }


# --------------------------------------------------------------------------- #
# Construção de DataFrames a partir dos registros crus
# --------------------------------------------------------------------------- #
def montar_dataframe(registros: list[dict]) -> pd.DataFrame:
    """Constrói o DataFrame: descarta a linha de cabeçalho, valida o schema e coage V->float."""
    exigir_nao_nulo(registros, "registros", operacao="montar_dataframe")
    if len(registros) <= 1:
        raise TransformError(
            "Registros insuficientes do SIDRA (apenas cabeçalho ou vazio)",
            contexto={"linhas": len(registros)},
        )
    df = pd.DataFrame(registros).iloc[1:].reset_index(drop=True)
    df = validar_bruto(df)
    df = df.assign(valor=df["V"].map(_para_float))
    return df


def _periodo_mais_recente(df: pd.DataFrame) -> str:
    # D3C é AAAAMM; comparação lexicográfica == cronológica.
    return str(df["D3C"].max())


def _item_de(df: pd.DataFrame, codigo_categoria: str, periodo: str) -> ItemVariacao:
    sub = df[(df["D4C"] == codigo_categoria) & (df["D3C"] == periodo)]
    if sub.empty:
        raise TransformError(
            "Categoria/atividade ausente no período",
            contexto={"categoria": codigo_categoria, "periodo": periodo},
        )

    def valor(variavel: str) -> float:
        linha = sub[sub["D2C"] == variavel]["valor"]
        return float(linha.iloc[0]) if not linha.empty else math.nan

    return ItemVariacao(
        nome=_limpar_nome(str(sub["D4N"].iloc[0])),
        codigo=codigo_categoria,
        var_mensal=valor(config.VAR_VAR_MENSAL),
        var_interanual=valor(config.VAR_INTERANUAL),
        acum_ano=valor(config.VAR_ACUM_ANO),
        acum_12m=valor(config.VAR_ACUM_12M),
    )


def _valor_variavel(df: pd.DataFrame, categoria: str, variavel: str, periodo: str) -> float:
    linha = df[(df["D4C"] == categoria) & (df["D2C"] == variavel) & (df["D3C"] == periodo)]["valor"]
    return float(linha.iloc[0]) if not linha.empty else math.nan


def _destaques(
    df_ativ: pd.DataFrame, periodo: str, *, quantidade: int = 3
) -> tuple[list[ItemVariacao], list[ItemVariacao]]:
    """Maiores altas/baixas entre atividades detalhadas (exclui os agregados de seção)."""
    agregados = {config.CAT_INDUSTRIA_GERAL, config.CAT_EXTRATIVA, config.CAT_TRANSFORMACAO}
    detalhadas = df_ativ[
        (df_ativ["D3C"] == periodo)
        & (df_ativ["D2C"] == config.VAR_INTERANUAL)
        & (~df_ativ["D4C"].isin(agregados))
    ].copy()
    detalhadas = detalhadas[detalhadas["valor"].notna()]
    if detalhadas.empty:
        return [], []

    ordenado = detalhadas.sort_values("valor", ascending=False)

    def construir(linhas: pd.DataFrame) -> list[ItemVariacao]:
        return [_item_de(df_ativ, str(c), periodo) for c in linhas["D4C"].tolist()]

    altas = construir(ordenado.head(quantidade))
    baixas = construir(ordenado.tail(quantidade).iloc[::-1])
    return altas, baixas


def _serie_dessaz(df_serie: pd.DataFrame) -> list[tuple[str, float]]:
    serie = df_serie[
        (df_serie["D4C"] == config.CAT_INDUSTRIA_GERAL)
        & (df_serie["D2C"] == config.VAR_INDICE_DESSAZ)
    ].sort_values("D3C")
    pontos = [(str(p), float(v)) for p, v in zip(serie["D3C"], serie["valor"], strict=True)]
    if not pontos:
        raise TransformError("Série do índice dessazonalizado vazia", contexto={})
    return pontos


# --------------------------------------------------------------------------- #
# Montagem do resultado completo
# --------------------------------------------------------------------------- #
def construir_dados(
    pacote: dict,
    *,
    data_extracao: dt.date,
    de_cache: bool = False,
    data_cache: dt.date | None = None,
) -> DadosPim:
    """Monta :class:`DadosPim` a partir do pacote cru (3 consultas SIDRA).

    ``pacote`` tem as chaves ``"atividades"`` (8888, último período, 5 variáveis),
    ``"serie"`` (8888, indústria geral, índice dessaz, 36 meses) e ``"categorias"``
    (8887, grandes categorias econômicas, 4 leituras).
    """
    exigir_nao_nulo(pacote, "pacote", operacao="construir_dados")
    for chave in ("atividades", "serie", "categorias"):
        if chave not in pacote:
            raise TransformError("Pacote cru incompleto", contexto={"chave_ausente": chave})

    df_ativ = montar_dataframe(pacote["atividades"])
    df_serie = montar_dataframe(pacote["serie"])
    df_cat = montar_dataframe(pacote["categorias"])

    periodo = _periodo_mais_recente(df_ativ)
    periodo_nome = str(df_ativ[df_ativ["D3C"] == periodo]["D3N"].iloc[0])

    industria_geral = _item_de(df_ativ, config.CAT_INDUSTRIA_GERAL, periodo)
    indice_dessaz = _valor_variavel(
        df_ativ, config.CAT_INDUSTRIA_GERAL, config.VAR_INDICE_DESSAZ, periodo
    )
    secoes = [
        _item_de(df_ativ, config.CAT_EXTRATIVA, periodo),
        _item_de(df_ativ, config.CAT_TRANSFORMACAO, periodo),
    ]

    periodo_cat = _periodo_mais_recente(df_cat)
    categorias_economicas = [
        _item_de(df_cat, codigo, periodo_cat) for codigo in config.GRANDES_CATEGORIAS.values()
    ]

    maiores_altas, maiores_baixas = _destaques(df_ativ, periodo)
    serie_indice = _serie_dessaz(df_serie)

    return DadosPim(
        periodo=periodo,
        periodo_nome=periodo_nome,
        industria_geral=industria_geral,
        indice_dessaz=indice_dessaz,
        secoes=secoes,
        categorias_economicas=categorias_economicas,
        maiores_altas=maiores_altas,
        maiores_baixas=maiores_baixas,
        serie_indice=serie_indice,
        data_extracao=data_extracao,
        de_cache=de_cache,
        data_cache=data_cache,
    )
