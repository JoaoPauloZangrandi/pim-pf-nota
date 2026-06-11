"""Testes da Etapa 2 — cache cru e modo de degradação."""

from __future__ import annotations

import datetime as dt

import pytest

from pim_report.cache import CacheBruto, carregar_mais_recente, salvar_bruto
from pim_report.exceptions import CacheVazioError, InvalidParameterError

REGISTROS = [{"cabecalho": "x"}, {"V": "1.2", "D3C": "202604"}]


def test_salvar_e_carregar_roundtrip(tmp_path):
    salvar_bruto(REGISTROS, data=dt.date(2026, 6, 11), dir_cache=tmp_path)
    cache = carregar_mais_recente(dir_cache=tmp_path)
    assert isinstance(cache, CacheBruto)
    assert cache.registros == REGISTROS
    assert cache.data_origem == dt.date(2026, 6, 11)


def test_carrega_o_mais_recente_entre_varios(tmp_path):
    salvar_bruto(REGISTROS, data=dt.date(2026, 4, 1), dir_cache=tmp_path)
    salvar_bruto(REGISTROS, data=dt.date(2026, 6, 11), dir_cache=tmp_path)
    cache = carregar_mais_recente(dir_cache=tmp_path)
    assert cache.data_origem == dt.date(2026, 6, 11)


def test_sem_cache_levanta_cache_vazio(tmp_path):
    with pytest.raises(CacheVazioError):
        carregar_mais_recente(dir_cache=tmp_path)


def test_salvar_none_e_rejeitado(tmp_path):
    with pytest.raises(InvalidParameterError):
        salvar_bruto(None, dir_cache=tmp_path)
