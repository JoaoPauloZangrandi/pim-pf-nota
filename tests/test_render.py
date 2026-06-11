"""Testes da Etapa 0 — render LaTeX: FORÇAR FALHA DE COMPILAÇÃO PRIMEIRO (TDD, vermelho).

Enquanto ``pim_report.render_latex.compilar_pdf`` não existir (Etapa 5), estes testes falham.

Design pensado para robustez E testabilidade: ``compilar_pdf`` aceita um ``runner`` injetável
(por padrão chama ``latexmk`` via subprocess). Nos testes injetamos um runner falso que simula
o latexmk falhando — assim testamos o tratamento de erro SEM depender de uma instalação TeX,
o que mantém o CI leve. Em falha, deve levantar :class:`LatexCompilationError` com contexto
(o ``.log`` capturado) — Martin, princípios 1, 4 e 5.
"""

from __future__ import annotations

import subprocess

import pytest

from pim_report.exceptions import InvalidParameterError, LatexCompilationError
from pim_report.render_latex import compilar_pdf

TEX_QUEBRADO = r"\documentclass{article}\begin{document"  # sem \end{document}


def _runner_que_falha(cmd, **kwargs):
    """Simula o latexmk retornando código de erro com mensagem típica de LaTeX."""
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=1,
        stdout="Running latexmk...",
        stderr="! LaTeX Error: \\begin{document} ended by \\end{...}.",
    )


def test_latex_quebrado_levanta_latex_compilation_error(tmp_path):
    with pytest.raises(LatexCompilationError):
        compilar_pdf(
            tex=TEX_QUEBRADO,
            destino=tmp_path,
            nome_base="nota_pim_2025-04",
            runner=_runner_que_falha,
        )


def test_falha_preserva_o_log_para_diagnostico(tmp_path):
    with pytest.raises(LatexCompilationError) as info:
        compilar_pdf(
            tex=TEX_QUEBRADO,
            destino=tmp_path,
            nome_base="nota_pim_2025-04",
            runner=_runner_que_falha,
        )
    # Princípio 4: a exceção dá contexto acionável — o caminho do log capturado.
    assert info.value.log_path is not None


def test_parametros_none_sao_rejeitados(tmp_path):
    # Princípio 8: não passe None pela fronteira do render.
    with pytest.raises(InvalidParameterError):
        compilar_pdf(tex=None, destino=tmp_path, nome_base="nota", runner=_runner_que_falha)
    with pytest.raises(InvalidParameterError):
        compilar_pdf(tex=TEX_QUEBRADO, destino=None, nome_base="nota", runner=_runner_que_falha)
    with pytest.raises(InvalidParameterError):
        compilar_pdf(tex=TEX_QUEBRADO, destino=tmp_path, nome_base=None, runner=_runner_que_falha)
