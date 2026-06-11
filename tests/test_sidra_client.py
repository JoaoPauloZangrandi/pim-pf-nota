"""Testes da Etapa 0 — wrapper SIDRA: FORÇAR EXCEÇÕES PRIMEIRO (TDD, vermelho).

Estes testes definem o contrato do cliente antes de existir lógica feliz. Enquanto
``pim_report.sidra_client.SidraClient`` não estiver implementado (Etapa 1), eles falham —
exatamente o estado vermelho que o Cap.7 do Martin prega (escrever try/except e os testes
de erro primeiro).

Cada teste valida que um erro de terceiros (``requests``) é TRADUZIDO para a família de
exceções de domínio :class:`SidraError` (Martin, princípio 5 — isolar a dependência).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import requests
import responses

from pim_report.exceptions import (
    InvalidParameterError,
    SidraConnectionError,
    SidraEmptyError,
    SidraError,
    SidraHTTPError,
    SidraPayloadError,
)
from pim_report.sidra_client import SidraClient

FIXTURES = Path(__file__).parent / "fixtures"
SIDRA_URL = re.compile(r"https://apisidra\.ibge\.gov\.br/.*")

CONSULTA = {"tabela": "8888", "variaveis": "11602", "periodo": "202504"}


@pytest.fixture
def client() -> SidraClient:
    # espera_inicial=0 mantém os testes rápidos (sem dormir entre retentativas).
    return SidraClient(timeout=5, max_tentativas=3, espera_inicial=0)


@responses.activate
def test_timeout_e_traduzido_para_sidra_connection_error(client):
    responses.add(responses.GET, SIDRA_URL, body=requests.exceptions.ConnectTimeout("estourou"))
    with pytest.raises(SidraConnectionError) as info:
        client.buscar_tabela(**CONSULTA)
    assert isinstance(info.value, SidraError)
    # Princípio 4: encadeamento preserva a causa original de terceiros.
    assert info.value.__cause__ is not None


@responses.activate
def test_erro_5xx_e_traduzido_para_sidra_http_error(client):
    for _ in range(5):
        responses.add(responses.GET, SIDRA_URL, status=503, json={"erro": "indisponivel"})
    with pytest.raises(SidraHTTPError) as info:
        client.buscar_tabela(**CONSULTA)
    assert info.value.status_code == 503
    assert info.value.transitorio is True


@responses.activate
def test_json_malformado_e_traduzido_para_payload_error(client):
    corpo = (FIXTURES / "sidra_resposta_malformada.json").read_text(encoding="utf-8")
    responses.add(responses.GET, SIDRA_URL, body=corpo, status=200, content_type="application/json")
    with pytest.raises(SidraPayloadError):
        client.buscar_tabela(**CONSULTA)


@responses.activate
def test_resposta_vazia_e_traduzida_para_empty_error(client):
    corpo = json.loads((FIXTURES / "sidra_resposta_vazia.json").read_text(encoding="utf-8"))
    responses.add(responses.GET, SIDRA_URL, json=corpo, status=200)
    with pytest.raises(SidraEmptyError):
        client.buscar_tabela(**CONSULTA)


@responses.activate
def test_resposta_feliz_retorna_lista_nao_vazia_e_nunca_none(client):
    dados = json.loads((FIXTURES / "sidra_resposta_feliz.json").read_text(encoding="utf-8"))
    responses.add(responses.GET, SIDRA_URL, json=dados, status=200)
    registros = client.buscar_tabela(**CONSULTA)
    # Princípios 1 e 7: sucesso devolve coleção concreta, nunca None.
    assert registros is not None
    assert isinstance(registros, list)
    assert len(registros) >= 1


def test_parametros_none_sao_rejeitados_na_fronteira(client):
    # Princípio 8: validar parâmetros e proibir None.
    with pytest.raises(InvalidParameterError):
        client.buscar_tabela(tabela=None, variaveis="11602", periodo="202504")
    with pytest.raises(InvalidParameterError):
        client.buscar_tabela(tabela="8888", variaveis=None, periodo="202504")
    with pytest.raises(InvalidParameterError):
        client.buscar_tabela(tabela="8888", variaveis="11602", periodo=None)
