"""sidra_client.py — WRAPPER da API SIDRA (Martin Cap.7, princípio 5).

Este é o ÚNICO ponto do sistema que conhece ``requests``/SIDRA. Ele traduz toda falha de
terceiros (timeout, conexão, 4xx/5xx, JSON malformado, resposta vazia) para a família de
exceções de domínio :class:`~pim_report.exceptions.SidraError`. Assim o resto do código
depende apenas do domínio — trocar a biblioteca de acesso (``sidrapy`` ↔ ``requests``) não
afeta nenhum outro módulo.

Robustez (princípio do exercício):
- **Timeout explícito** em toda requisição.
- **Retentativa com backoff exponencial** (``tenacity``) APENAS em erros transitórios
  (conexão/timeout e HTTP 5xx). Erros definitivos (4xx, payload inválido, vazio) falham na hora.
- **Sem None cruzando fronteiras** (princípios 1, 7, 8): parâmetros obrigatórios são validados;
  sucesso devolve uma lista concreta; qualquer problema vira exceção.
"""

from __future__ import annotations

import logging

import requests
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from . import config
from .exceptions import (
    SidraConnectionError,
    SidraEmptyError,
    SidraHTTPError,
    SidraPayloadError,
    exigir_nao_nulo,
)

logger = logging.getLogger(__name__)


def _e_transitorio(exc: BaseException) -> bool:
    """Define o que merece retentativa: conexão/timeout e HTTP 5xx."""
    if isinstance(exc, SidraConnectionError):
        return True
    if isinstance(exc, SidraHTTPError):
        return exc.transitorio
    return False


class SidraClient:
    """Cliente robusto da API de valores do SIDRA.

    Args:
        timeout: tempo máximo (s) por requisição.
        max_tentativas: número total de tentativas em erros transitórios.
        espera_inicial: base (s) do backoff exponencial entre tentativas.
        espera_maxima: teto (s) do backoff.
        base_url: raiz da API (parametrizável para testes).
        session: ``requests.Session`` injetável (testes/conexões reutilizadas).
    """

    def __init__(
        self,
        *,
        timeout: float = config.HTTP_TIMEOUT_SEGUNDOS,
        max_tentativas: int = config.MAX_TENTATIVAS,
        espera_inicial: float = config.ESPERA_INICIAL_SEGUNDOS,
        espera_maxima: float = config.ESPERA_MAXIMA_SEGUNDOS,
        base_url: str = config.SIDRA_BASE_URL,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_tentativas = max_tentativas
        self.espera_inicial = espera_inicial
        self.espera_maxima = espera_maxima
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def montar_url(
        self,
        *,
        tabela: str,
        variaveis: str,
        periodo: str,
        nivel: str = config.SIDRA_NIVEL_TERRITORIAL,
        territorio: str = config.SIDRA_TERRITORIO,
        classificacao: str | None = None,
        categorias: str | None = None,
    ) -> str:
        """Monta a URL no formato /values/t/{t}/{n}/{terr}/v/{vars}/p/{periodo}[/c{cl}/{cats}]."""
        url = (
            f"{self.base_url}/values/t/{tabela}"
            f"/{nivel}/{territorio}"
            f"/v/{variaveis}"
            f"/p/{periodo}"
        )
        if classificacao is not None and categorias is not None:
            url += f"/c{classificacao}/{categorias}"
        return url

    def buscar_tabela(
        self,
        *,
        tabela: str,
        variaveis: str,
        periodo: str,
        nivel: str = config.SIDRA_NIVEL_TERRITORIAL,
        territorio: str = config.SIDRA_TERRITORIO,
        classificacao: str | None = None,
        categorias: str | None = None,
    ) -> list[dict]:
        """Consulta a tabela e devolve a lista crua de registros (inclui a linha de cabeçalho).

        Levanta uma exceção :class:`SidraError` específica em qualquer falha; nunca retorna
        ``None`` nem lista vazia silenciosa.
        """
        exigir_nao_nulo(tabela, "tabela", operacao="buscar_tabela")
        exigir_nao_nulo(variaveis, "variaveis", operacao="buscar_tabela")
        exigir_nao_nulo(periodo, "periodo", operacao="buscar_tabela")

        url = self.montar_url(
            tabela=tabela,
            variaveis=variaveis,
            periodo=periodo,
            nivel=nivel,
            territorio=territorio,
            classificacao=classificacao,
            categorias=categorias,
        )
        logger.info("Consultando SIDRA: tabela=%s periodo=%s url=%s", tabela, periodo, url)

        retrying = Retrying(
            stop=stop_after_attempt(self.max_tentativas),
            wait=wait_exponential(multiplier=self.espera_inicial, max=self.espera_maxima),
            retry=retry_if_exception(_e_transitorio),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        registros = retrying(self._executar_requisicao, url)
        logger.info("SIDRA respondeu %d registros (tabela=%s)", len(registros), tabela)
        return registros

    # ------------------------------------------------------------------ #
    # Núcleo: uma tentativa + tradução de erros de terceiros
    # ------------------------------------------------------------------ #
    def _executar_requisicao(self, url: str) -> list[dict]:
        try:
            resposta = self._session.get(url, timeout=self.timeout)
        except (requests.Timeout, requests.ConnectionError) as erro:
            raise SidraConnectionError(
                "Falha de conexão/timeout ao consultar o SIDRA",
                contexto={"url": url, "timeout": self.timeout},
            ) from erro
        except requests.RequestException as erro:
            raise SidraConnectionError(
                "Erro inesperado de requisição ao SIDRA",
                contexto={"url": url},
            ) from erro

        if resposta.status_code >= 400:
            raise SidraHTTPError(
                f"SIDRA respondeu com HTTP {resposta.status_code}",
                status_code=resposta.status_code,
                contexto={"url": url},
            )

        try:
            dados = resposta.json()
        except ValueError as erro:  # inclui json.JSONDecodeError
            raise SidraPayloadError(
                "Resposta do SIDRA não é JSON válido",
                contexto={"url": url},
            ) from erro

        if not isinstance(dados, list):
            raise SidraPayloadError(
                "Estrutura inesperada do SIDRA: esperava uma lista de registros",
                contexto={"url": url, "tipo_recebido": type(dados).__name__},
            )

        # O SIDRA devolve a primeira linha como cabeçalho de rótulos; dados úteis vêm depois.
        if len(dados) <= 1:
            raise SidraEmptyError(
                "Consulta ao SIDRA sem registros de dados (possível período não publicado)",
                contexto={"url": url, "linhas": len(dados)},
            )

        return dados
