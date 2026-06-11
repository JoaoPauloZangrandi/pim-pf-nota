"""Smoke test end-to-end do pipeline (Etapa 7/8), com cliente e compilador falsos.

Não toca a rede nem o TeX: o cliente devolve o pacote sintético e o runner do LaTeX simula
uma compilação bem-sucedida criando o PDF. Verifica também o Special Case e a degradação.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

import pytest

from pim_report import config
from pim_report.cache import salvar_bruto
from pim_report.exceptions import CacheVazioError, SidraConnectionError
from pim_report.pipeline import gerar_nota


class _ClienteFalso:
    def __init__(self, pacote: dict, *, falhar: bool = False):
        self.pacote = pacote
        self.falhar = falhar

    def buscar_tabela(self, *, tabela, variaveis, periodo, classificacao=None, categorias=None):
        if self.falhar:
            raise SidraConnectionError("rede fora (teste)", contexto={})
        if tabela == config.TABELA_CATEGORIAS:
            return self.pacote["categorias"]
        if variaveis == config.VAR_INDICE_DESSAZ:
            return self.pacote["serie"]
        return self.pacote["atividades"]


def _runner_ok(cmd, **kwargs):
    """Simula latexmk: cria o PDF esperado e retorna sucesso."""
    Path(cmd[-1]).with_suffix(".pdf").write_bytes(b"%PDF-1.4 fake\n%%EOF\n")
    return subprocess.CompletedProcess(cmd, 0, "ok", "")


def test_pipeline_gera_pdf_e_html(pacote_exemplo, tmp_path):
    saida, cache = tmp_path / "out", tmp_path / "cache"
    execucao = gerar_nota(
        "last",
        client=_ClienteFalso(pacote_exemplo),
        dir_saida=saida,
        dir_cache=cache,
        runner=_runner_ok,
    )
    assert execucao.publicado is True
    assert execucao.periodo == "202604"
    assert execucao.pdf.exists()
    assert execucao.html.exists()
    assert execucao.pdf.name == "nota_pim_2026-04.pdf"
    # cache cru foi gravado
    assert list(cache.glob("*.json"))
    # HTML é autossuficiente e mapeia os princípios
    texto = execucao.html.read_text(encoding="utf-8")
    assert "Princípio 5" in texto
    assert "data:image/png;base64," in texto


def test_periodo_futuro_retorna_special_case(pacote_exemplo, tmp_path):
    execucao = gerar_nota(
        "209912",
        client=_ClienteFalso(pacote_exemplo),
        dir_saida=tmp_path / "out",
        dir_cache=tmp_path / "cache",
        runner=_runner_ok,
    )
    assert execucao.publicado is False
    assert execucao.pdf is None
    assert "ainda não publicada" in execucao.mensagem


def test_degradacao_usa_cache_quando_api_cai(pacote_exemplo, tmp_path):
    cache = tmp_path / "cache"
    salvar_bruto(pacote_exemplo, data=dt.date(2026, 6, 1), dir_cache=cache)
    execucao = gerar_nota(
        "last",
        client=_ClienteFalso(pacote_exemplo, falhar=True),
        dir_saida=tmp_path / "out",
        dir_cache=cache,
        runner=_runner_ok,
    )
    assert execucao.publicado is True
    assert execucao.de_cache is True
    assert "CACHE" in execucao.mensagem


def test_api_fora_e_sem_cache_falha_acionavel(pacote_exemplo, tmp_path):
    with pytest.raises(CacheVazioError):
        gerar_nota(
            "last",
            client=_ClienteFalso(pacote_exemplo, falhar=True),
            dir_saida=tmp_path / "out",
            dir_cache=tmp_path / "cache_vazio",
            runner=_runner_ok,
        )
