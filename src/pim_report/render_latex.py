"""render_latex.py — Jinja2 -> .tex -> PDF (build determinístico).

Robustez (Martin, princípios 1, 4, 5):
- ``compilar_pdf`` recebe um ``runner`` injetável (por padrão chama ``latexmk`` via subprocess).
  Isso permite testar o tratamento de falha SEM uma instalação TeX (CI leve).
- Captura stdout/stderr e o ``.log``; em falha, preserva o log e levanta
  :class:`LatexCompilationError` com o caminho do log no contexto.
- Sem None cruzando fronteiras: parâmetros são validados.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import config
from .analysis import Narrativa, formatar_pct
from .charts import Graficos
from .exceptions import LatexCompilationError, RenderError, exigir_nao_nulo
from .transform import DadosPim

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess]


def _latex_escape(texto: object) -> str:
    """Escapa caracteres especiais do LaTeX em texto vindo dos dados."""
    s = str(texto)
    subs = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for alvo, rep in subs.items():
        s = s.replace(alvo, rep)
    return s


def _ambiente_jinja(dir_templates: Path) -> Environment:
    """Ambiente Jinja com delimitadores que não conflitam com as chaves do LaTeX."""
    env = Environment(
        block_start_string="((*",
        block_end_string="*))",
        variable_start_string="(((",
        variable_end_string=")))",
        comment_start_string="((=",
        comment_end_string="=))",
        loader=FileSystemLoader(str(dir_templates)),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tex"] = _latex_escape
    env.filters["pct"] = formatar_pct
    return env


def _runner_subprocess(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _comandos_candidatos(destino: Path, caminho_tex: Path) -> list[list[str]]:
    """Compiladores em ordem de preferência: latexmk (mais reprodutível), depois pdflatex.

    O fallback torna a esteira robusta a instalações em que o latexmk não funciona (ex.: MiKTeX
    sem Perl); o pdflatex do próprio MiKTeX dá conta da nota, que não tem referências cruzadas.
    """
    base = [f"-output-directory={destino}", str(caminho_tex)]
    return [
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", *base],
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", *base],
    ]


def compilar_pdf(
    *,
    tex: str,
    destino: Path,
    nome_base: str,
    runner: Runner | None = None,
) -> Path:
    """Escreve ``nome_base.tex`` em ``destino``, compila e devolve o caminho do PDF.

    Tenta cada compilador candidato em ordem; o primeiro que gerar o PDF vence. Se todos
    falharem, preserva o ``.log`` e levanta :class:`LatexCompilationError` com o histórico.
    """
    exigir_nao_nulo(tex, "tex", operacao="compilar_pdf")
    exigir_nao_nulo(destino, "destino", operacao="compilar_pdf")
    exigir_nao_nulo(nome_base, "nome_base", operacao="compilar_pdf")

    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    caminho_tex = destino / f"{nome_base}.tex"
    caminho_pdf = destino / f"{nome_base}.pdf"
    caminho_log = destino / f"{nome_base}.log"
    caminho_tex.write_text(tex, encoding="utf-8")

    executar = runner or _runner_subprocess
    tentativas: list[str] = []
    ultimo: subprocess.CompletedProcess | None = None

    for cmd in _comandos_candidatos(destino, caminho_tex):
        logger.info("Compilando LaTeX: %s", " ".join(cmd))
        try:
            ultimo = executar(cmd, cwd=str(destino))
        except FileNotFoundError:
            tentativas.append(f"{cmd[0]}: não encontrado no PATH")
            continue
        if ultimo.returncode == 0 and caminho_pdf.exists():
            logger.info("PDF gerado via %s: %s", cmd[0], caminho_pdf)
            return caminho_pdf
        tentativas.append(f"{cmd[0]}: returncode={ultimo.returncode}")

    # Todos falharam: preserva o log para diagnóstico (princípio 4 — contexto).
    if not caminho_log.exists() and ultimo is not None:
        caminho_log.write_text(
            (ultimo.stdout or "") + "\n--- STDERR ---\n" + (ultimo.stderr or ""),
            encoding="utf-8",
        )
    raise LatexCompilationError(
        "Falha ao compilar o LaTeX da nota (nenhum compilador disponível teve sucesso)",
        log_path=str(caminho_log) if caminho_log.exists() else None,
        contexto={"tentativas": tentativas, "tex": str(caminho_tex)},
    )


def renderizar_nota(
    dados: DadosPim,
    narrativa: Narrativa,
    graficos: Graficos,
    *,
    dir_saida: Path = config.DIR_OUTPUT,
    dir_templates: Path = config.DIR_TEMPLATES,
    runner: Runner | None = None,
) -> Path:
    """Renderiza o template, compila e devolve o caminho do PDF ``nota_pim_AAAA-MM.pdf``."""
    exigir_nao_nulo(dados, "dados", operacao="renderizar_nota")
    exigir_nao_nulo(narrativa, "narrativa", operacao="renderizar_nota")
    exigir_nao_nulo(graficos, "graficos", operacao="renderizar_nota")

    env = _ambiente_jinja(dir_templates)
    try:
        template = env.get_template("nota.tex.j2")
    except Exception as erro:  # jinja TemplateNotFound etc.
        raise RenderError(
            "Template LaTeX da nota não encontrado/inválido",
            contexto={"dir_templates": str(dir_templates)},
        ) from erro

    tex = template.render(
        dados=dados,
        narrativa=narrativa,
        # caminhos absolutos POSIX para o \includegraphics
        grafico_serie=graficos.serie_pdf.as_posix(),
        grafico_categorias=graficos.categorias_pdf.as_posix(),
    )

    nome_base = f"nota_pim_{dados.periodo[:4]}-{dados.periodo[4:6]}"
    pdf = compilar_pdf(tex=tex, destino=dir_saida, nome_base=nome_base, runner=runner)
    # Limpa subprodutos de compilação, mantendo .tex, .pdf (e .log em caso de falha já tratado).
    _limpar_subprodutos(dir_saida, nome_base)
    return pdf


def _limpar_subprodutos(dir_saida: Path, nome_base: str) -> None:
    for ext in (".aux", ".fls", ".fdb_latexmk", ".out", ".log", ".synctex.gz"):
        alvo = dir_saida / f"{nome_base}{ext}"
        if alvo.exists():
            try:
                alvo.unlink()
            except OSError:
                shutil.rmtree(alvo, ignore_errors=True)
