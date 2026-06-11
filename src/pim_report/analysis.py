"""analysis.py — narrativa determinística da nota.

Deriva manchete, subtítulo, destaques e parágrafo de contexto EXCLUSIVAMENTE dos dados
(:class:`~pim_report.transform.DadosPim`). Nada é inventado: as frases seguem regras fixas
sobre os sinais e as magnitudes das leituras (no espírito da matéria do IBGE citada no
enunciado, que contextualiza o número em vez de só reportá-lo).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .exceptions import AnalysisError, exigir_nao_nulo
from .transform import DadosPim, ItemVariacao

_LIMIAR_ESTAVEL = 0.05  # |variação| abaixo disso é tratada como estabilidade


def formatar_pct(valor: float) -> str:
    """Formata a variação em padrão brasileiro com sinal: 1.23 -> '+1,2%'; NaN -> 'n/d'."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "n/d"
    return f"{valor:+.1f}%".replace(".", ",")


def _verbo(valor: float) -> str:
    if math.isnan(valor):
        return "não disponível"
    if valor > _LIMIAR_ESTAVEL:
        return "avançou"
    if valor < -_LIMIAR_ESTAVEL:
        return "recuou"
    return "ficou praticamente estável"


def _magnitude(valor: float) -> str:
    """|x| em padrão brasileiro, sem sinal (para anexar ao verbo)."""
    if math.isnan(valor):
        return ""
    return f"{abs(valor):.1f}%".replace(".", ",")


@dataclass(frozen=True)
class Narrativa:
    manchete: str
    subtitulo: str
    paragrafo_contexto: str
    texto_altas: str
    texto_baixas: str
    texto_categorias: str


def _frase_variacao(rotulo: str, valor: float) -> str:
    verbo = _verbo(valor)
    if verbo == "ficou praticamente estável" or verbo == "não disponível":
        return f"{rotulo} {verbo}"
    return f"{rotulo} {verbo} {_magnitude(valor)}"


def _texto_destaques(itens: list[ItemVariacao], rotulo: str) -> str:
    if not itens:
        return f"Não há {rotulo} com dado interanual disponível neste período."
    partes = [f"{it.nome} ({formatar_pct(it.var_interanual)})" for it in itens]
    return f"{rotulo.capitalize()}: " + "; ".join(partes) + "."


def _texto_categorias(dados: DadosPim) -> str:
    if not dados.categorias_economicas:
        return "Sem dados por categorias econômicas neste período."
    partes = [
        f"{cat.nome.lower()} {_verbo(cat.var_mensal)} {_magnitude(cat.var_mensal)}".strip()
        for cat in dados.categorias_economicas
    ]
    return (
        "Entre as grandes categorias econômicas (m/m-1, com ajuste sazonal), "
        + "; ".join(partes)
        + "."
    )


def _paragrafo_contexto(dados: DadosPim) -> str:
    ig = dados.industria_geral
    mensal, interanual, ano, doze = ig.var_mensal, ig.var_interanual, ig.acum_ano, ig.acum_12m

    abertura = (
        f"Em {dados.periodo_nome}, a produção industrial brasileira "
        f"{_verbo(mensal)} {_magnitude(mensal)} ante o mês anterior na série com ajuste "
        f"sazonal, com o índice dessazonalizado em {dados.indice_dessaz:.1f} pontos "
        f"(base 2022=100)."
    ).replace(" .", ".")

    # Regra determinística: relação entre o resultado mensal e a tendência de 12 meses.
    if not math.isnan(mensal) and not math.isnan(doze):
        if mensal > _LIMIAR_ESTAVEL and doze < -_LIMIAR_ESTAVEL:
            tendencia = (
                "O resultado mensal positivo contrasta com a retração ainda observada no "
                "acumulado em 12 meses, sugerindo recuperação incipiente sobre base fraca."
            )
        elif mensal < -_LIMIAR_ESTAVEL and doze > _LIMIAR_ESTAVEL:
            tendencia = (
                "Apesar da queda no mês, o acumulado em 12 meses segue positivo, indicando "
                "acomodação após período de expansão."
            )
        elif mensal > _LIMIAR_ESTAVEL and doze > _LIMIAR_ESTAVEL:
            tendencia = (
                "O avanço mensal reforça a trajetória de alta também observada no acumulado "
                "em 12 meses."
            )
        elif mensal < -_LIMIAR_ESTAVEL and doze < -_LIMIAR_ESTAVEL:
            tendencia = (
                "A queda no mês soma-se à retração do acumulado em 12 meses, configurando "
                "tendência de enfraquecimento."
            )
        else:
            tendencia = (
                "Os movimentos no mês e no acumulado em 12 meses são modestos, indicando "
                "relativa estabilidade da atividade industrial."
            )
    else:
        tendencia = (
            "Parte das leituras não está disponível neste período, limitando a leitura de "
            "tendência."
        )

    comparativos = (
        f"Na comparação interanual, a indústria {_frase_variacao('', interanual).strip()}; "
        f"no acumulado do ano, {_frase_variacao('', ano).strip()}."
    )

    return f"{abertura} {comparativos} {tendencia}"


def gerar_narrativa(dados: DadosPim) -> Narrativa:
    """Gera a narrativa determinística da nota a partir de :class:`DadosPim`."""
    exigir_nao_nulo(dados, "dados", operacao="gerar_narrativa")
    if not getattr(dados, "publicado", False):
        raise AnalysisError(
            "Narrativa só pode ser gerada para um período publicado",
            contexto={"tipo": type(dados).__name__},
        )

    ig = dados.industria_geral
    manchete = (
        (
            f"Produção industrial {_verbo(ig.var_mensal)} {_magnitude(ig.var_mensal)} "
            f"em {dados.periodo_nome} (m/m-1, com ajuste sazonal)"
        )
        .replace("  ", " ")
        .strip()
    )

    subtitulo = (
        f"Interanual: {formatar_pct(ig.var_interanual)} · "
        f"Acumulado no ano: {formatar_pct(ig.acum_ano)} · "
        f"Em 12 meses: {formatar_pct(ig.acum_12m)}"
    )

    return Narrativa(
        manchete=manchete,
        subtitulo=subtitulo,
        paragrafo_contexto=_paragrafo_contexto(dados),
        texto_altas=_texto_destaques(dados.maiores_altas, "maiores altas"),
        texto_baixas=_texto_destaques(dados.maiores_baixas, "maiores baixas"),
        texto_categorias=_texto_categorias(dados),
    )
