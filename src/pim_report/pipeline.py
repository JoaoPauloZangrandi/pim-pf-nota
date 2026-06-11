"""pipeline.py — orquestração da esteira (try/except/finally escrito PRIMEIRO).

Garante o invariante do exercício: cada execução **produz um PDF válido** OU **falha com
mensagem acionável e log** — nunca um PDF silenciosamente errado. Coordena extração (com
degradação para cache), validação, transformação, narrativa, gráficos e render, com logging
em cada etapa. Trata o Special Case :class:`PeriodoNaoPublicado` sem gerar nota enganosa.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path

from . import config
from .analysis import gerar_narrativa
from .cache import carregar_mais_recente, salvar_bruto
from .charts import gerar_graficos
from .exceptions import PimReportError, SidraError, exigir_nao_nulo
from .render_html import renderizar_dossie, renderizar_relatorio
from .render_latex import renderizar_nota
from .sidra_client import SidraClient
from .special_cases import PeriodoNaoPublicado
from .transform import construir_dados, montar_dataframe

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Execucao:
    """Resultado de uma execução da esteira."""

    publicado: bool
    periodo: str
    pdf: Path | None
    html: Path | None
    de_cache: bool
    mensagem: str


def _periodo_menos(periodo: str, meses: int) -> str:
    ano, mes = int(periodo[:4]), int(periodo[4:6])
    indice = ano * 12 + (mes - 1) - meses
    a, m = divmod(indice, 12)
    return f"{a:04d}{m + 1:02d}"


def _ultimo_periodo_disponivel(registros: list[dict]) -> str:
    return str(montar_dataframe(registros)["D3C"].max())


def coletar_pacote(
    client: SidraClient, alvo: str, atividades_pronto: list[dict] | None = None
) -> dict:
    """Coleta as 3 consultas (atividades, série dessaz, categorias) para o período ``alvo``."""
    variaveis = ",".join(config.VARIAVEIS_PADRAO)
    leituras = ",".join(
        [config.VAR_VAR_MENSAL, config.VAR_INTERANUAL, config.VAR_ACUM_ANO, config.VAR_ACUM_12M]
    )

    if atividades_pronto is not None:
        atividades = atividades_pronto
    else:
        atividades = client.buscar_tabela(
            tabela=config.TABELA_ATIVIDADES,
            variaveis=variaveis,
            periodo=alvo,
            classificacao=config.CLASSIF_ATIVIDADES,
            categorias=config.CATEGORIAS_ATIVIDADES,
        )

    serie = client.buscar_tabela(
        tabela=config.TABELA_ATIVIDADES,
        variaveis=config.VAR_INDICE_DESSAZ,
        periodo=f"{_periodo_menos(alvo, 35)}-{alvo}",
        classificacao=config.CLASSIF_ATIVIDADES,
        categorias=config.CAT_INDUSTRIA_GERAL,
    )
    categorias = client.buscar_tabela(
        tabela=config.TABELA_CATEGORIAS,
        variaveis=leituras,
        periodo=alvo,
        classificacao=config.CLASSIF_CATEGORIAS,
        categorias="all",
    )
    return {"atividades": atividades, "serie": serie, "categorias": categorias}


def gerar_nota(
    periodo: str = "last",
    *,
    client: SidraClient | None = None,
    dir_saida: Path = config.DIR_OUTPUT,
    dir_cache: Path = config.DIR_DATA_RAW,
    runner=None,
) -> Execucao:
    """Executa a esteira completa. Veja o invariante no docstring do módulo."""
    exigir_nao_nulo(periodo, "periodo", operacao="gerar_nota")
    client = client or SidraClient()
    hoje = dt.date.today()
    de_cache = False
    data_cache: dt.date | None = None

    logger.info("=== Início da esteira PIM-PF (periodo=%s) ===", periodo)
    try:
        # --- Extração + checagem de publicação, com degradação para cache ---
        try:
            atividades_last = client.buscar_tabela(
                tabela=config.TABELA_ATIVIDADES,
                variaveis=",".join(config.VARIAVEIS_PADRAO),
                periodo="last",
                classificacao=config.CLASSIF_ATIVIDADES,
                categorias=config.CATEGORIAS_ATIVIDADES,
            )
            recente = _ultimo_periodo_disponivel(atividades_last)

            # Special Case: o mês pedido ainda não saiu -> não gera nota enganosa.
            if periodo != "last" and periodo > recente:
                snp = PeriodoNaoPublicado(periodo, recente, hoje)
                logger.warning(snp.mensagem())
                return Execucao(False, periodo, None, None, False, snp.mensagem())

            alvo = recente if periodo == "last" else periodo
            pacote = coletar_pacote(client, alvo, atividades_last if periodo == "last" else None)
            salvar_bruto(pacote, data=hoje, dir_cache=dir_cache)
            logger.info("Extração ao vivo concluída (alvo=%s)", alvo)
        except SidraError as erro:
            logger.warning("Falha na extração ao vivo (%s); tentando cache.", erro)
            cache = carregar_mais_recente(dir_cache=dir_cache)  # CacheVazioError se não houver
            pacote, de_cache, data_cache = cache.registros, True, cache.data_origem

        # --- Transformação + análise ---
        dados = construir_dados(
            pacote, data_extracao=hoje, de_cache=de_cache, data_cache=data_cache
        )
        narrativa = gerar_narrativa(dados)
        logger.info("Transformação/análise concluídas (periodo=%s)", dados.periodo)

        # --- Gráficos + render (PDF e HTML) ---
        graficos = gerar_graficos(dados, dir_saida=dir_saida)
        pdf = renderizar_nota(dados, narrativa, graficos, dir_saida=dir_saida, runner=runner)
        html = renderizar_relatorio(dados, narrativa, graficos, dir_saida=dir_saida, pdf_path=pdf)
        renderizar_dossie(dados, narrativa, graficos, dir_saida=dir_saida, pdf_path=pdf)

        msg = f"Nota gerada para {dados.periodo_nome}: {pdf.name}"
        if de_cache and data_cache is not None:
            msg += f" (DADOS DE CACHE de {data_cache:%d/%m/%Y})"
        logger.info(msg)
        return Execucao(True, dados.periodo, pdf, html, de_cache, msg)

    except PimReportError as erro:
        logger.error("Esteira falhou: %s", erro, exc_info=True)
        raise
    finally:
        logger.info("=== Fim da esteira PIM-PF ===")
