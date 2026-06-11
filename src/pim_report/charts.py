"""charts.py — geração das figuras (PDF para LaTeX, PNG para HTML).

Duas figuras, estilo limpo:
1. Série do índice dessazonalizado da indústria geral (linha).
2. Variação mensal (m/m-1) das grandes categorias econômicas (barras com cor por sinal).

Cada figura é salva em PDF (vetorial, para \\includegraphics no LaTeX) e PNG (para embutir em
base64 no HTML). ``gerar_graficos`` valida entradas (sem None) e devolve os caminhos gerados.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sem display (essencial em CI/servidor)

import matplotlib.pyplot as plt  # noqa: E402

from . import config  # noqa: E402
from .exceptions import exigir_nao_nulo  # noqa: E402
from .transform import DadosPim  # noqa: E402

logger = logging.getLogger(__name__)

_MESES = {
    "01": "jan",
    "02": "fev",
    "03": "mar",
    "04": "abr",
    "05": "mai",
    "06": "jun",
    "07": "jul",
    "08": "ago",
    "09": "set",
    "10": "out",
    "11": "nov",
    "12": "dez",
}
_COR_POS = "#1b7837"
_COR_NEG = "#b2182b"
_COR_LINHA = "#2166ac"


def _rotulo_mes(periodo: str) -> str:
    return f"{_MESES.get(periodo[4:6], periodo[4:6])}/{periodo[2:4]}"


def _aplicar_estilo(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.tick_params(length=0)


@dataclass(frozen=True)
class Graficos:
    serie_pdf: Path
    serie_png: Path
    categorias_pdf: Path
    categorias_png: Path


def figura_serie(dados: DadosPim) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    periodos = [p for p, _ in dados.serie_indice]
    valores = [v for _, v in dados.serie_indice]
    ax.plot(periodos, valores, color=_COR_LINHA, linewidth=2.0, marker="o", markersize=3)
    ax.set_title("Produção industrial — índice dessazonalizado (2022=100)", fontsize=11)
    ax.set_ylabel("Índice")
    passo = max(1, len(periodos) // 8)
    ax.set_xticks(periodos[::passo])
    ax.set_xticklabels([_rotulo_mes(p) for p in periodos[::passo]], rotation=0, fontsize=8)
    _aplicar_estilo(ax)
    fig.tight_layout()
    return fig


def figura_categorias(dados: DadosPim) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    nomes = [c.nome for c in dados.categorias_economicas]
    valores = [c.var_mensal for c in dados.categorias_economicas]
    cores = [_COR_POS if (v == v and v >= 0) else _COR_NEG for v in valores]
    y = range(len(nomes))
    ax.barh(list(y), valores, color=cores)
    ax.set_yticks(list(y))
    ax.set_yticklabels(nomes, fontsize=9)
    ax.invert_yaxis()
    ax.axvline(0, color="#444444", linewidth=0.8)
    ax.set_title("Categorias econômicas — variação mensal (m/m-1, ajuste sazonal)", fontsize=11)
    ax.set_xlabel("%")
    for i, v in zip(y, valores, strict=True):
        if v == v:  # não-NaN
            ax.text(
                v,
                i,
                f" {v:+.1f}".replace(".", ","),
                va="center",
                ha="left" if v >= 0 else "right",
                fontsize=8,
            )
    _aplicar_estilo(ax)
    fig.tight_layout()
    return fig


def _salvar(fig: plt.Figure, caminho_pdf: Path, caminho_png: Path) -> None:
    fig.savefig(caminho_pdf, bbox_inches="tight")
    fig.savefig(caminho_png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def gerar_graficos(dados: DadosPim, *, dir_saida: Path = config.DIR_OUTPUT) -> Graficos:
    """Gera as duas figuras em PDF e PNG e devolve os caminhos."""
    exigir_nao_nulo(dados, "dados", operacao="gerar_graficos")
    exigir_nao_nulo(dir_saida, "dir_saida", operacao="gerar_graficos")
    dir_saida.mkdir(parents=True, exist_ok=True)

    serie_pdf = dir_saida / "grafico_serie.pdf"
    serie_png = dir_saida / "grafico_serie.png"
    cat_pdf = dir_saida / "grafico_categorias.pdf"
    cat_png = dir_saida / "grafico_categorias.png"

    _salvar(figura_serie(dados), serie_pdf, serie_png)
    _salvar(figura_categorias(dados), cat_pdf, cat_png)
    logger.info("Gráficos gerados em %s", dir_saida)

    return Graficos(
        serie_pdf=serie_pdf, serie_png=serie_png, categorias_pdf=cat_pdf, categorias_png=cat_png
    )
