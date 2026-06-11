"""cache.py — persistência dos JSONs crus + modo de degradação.

Cada execução grava o JSON cru em ``data/raw/AAAA-MM-DD.json``. Se a API estiver fora do ar,
o pipeline usa o cache mais recente e estampa um aviso destacado no PDF/HTML.

Sem None cruzando fronteiras (Martin, princípios 6, 7, 8): "não há cache" não vira ``None``,
e sim a exceção :class:`~pim_report.exceptions.CacheVazioError`. O conteúdo carregado vem
embrulhado num objeto :class:`CacheBruto` que sempre carrega a data de origem (para o aviso).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from . import config
from .exceptions import CacheError, CacheVazioError, exigir_nao_nulo

logger = logging.getLogger(__name__)

_PADRAO_ARQUIVO = "%Y-%m-%d"


@dataclass(frozen=True)
class CacheBruto:
    """Registros crus recuperados do cache, com a data do arquivo de origem."""

    registros: list[dict]
    data_origem: dt.date
    caminho: Path

    def __post_init__(self) -> None:
        exigir_nao_nulo(self.registros, "registros", operacao="CacheBruto")
        exigir_nao_nulo(self.data_origem, "data_origem", operacao="CacheBruto")


def salvar_bruto(
    registros: list[dict],
    *,
    data: dt.date | None = None,
    dir_cache: Path = config.DIR_DATA_RAW,
) -> Path:
    """Grava os registros crus em ``dir_cache/AAAA-MM-DD.json`` e devolve o caminho gravado."""
    exigir_nao_nulo(registros, "registros", operacao="salvar_bruto")
    data = data or dt.date.today()
    dir_cache.mkdir(parents=True, exist_ok=True)
    caminho = dir_cache / f"{data.strftime(_PADRAO_ARQUIVO)}.json"
    try:
        caminho.write_text(
            json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as erro:
        raise CacheError(
            "Falha ao gravar o cache cru", contexto={"caminho": str(caminho)}
        ) from erro
    logger.info("Cache gravado: %s (%d registros)", caminho, len(registros))
    return caminho


def carregar_mais_recente(dir_cache: Path = config.DIR_DATA_RAW) -> CacheBruto:
    """Carrega o cache mais recente disponível (modo de degradação).

    Raises:
        CacheVazioError: se não houver nenhum arquivo de cache.
    """
    arquivos = sorted(dir_cache.glob("*.json")) if dir_cache.exists() else []
    if not arquivos:
        raise CacheVazioError(
            "Nenhum cache disponível para o modo de degradação",
            contexto={"dir_cache": str(dir_cache)},
        )

    caminho = arquivos[-1]
    try:
        registros = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise CacheError(
            "Falha ao ler/decodificar o cache mais recente",
            contexto={"caminho": str(caminho)},
        ) from erro

    if not isinstance(registros, list) or not registros:
        raise CacheVazioError(
            "Cache mais recente está vazio ou corrompido",
            contexto={"caminho": str(caminho)},
        )

    data_origem = _data_do_nome(caminho)
    logger.warning("Usando cache de %s (modo de degradação)", data_origem)
    return CacheBruto(registros=registros, data_origem=data_origem, caminho=caminho)


def _data_do_nome(caminho: Path) -> dt.date:
    """Extrai a data do nome AAAA-MM-DD.json; cai para a mtime se o nome não casar."""
    try:
        return dt.datetime.strptime(caminho.stem, _PADRAO_ARQUIVO).date()
    except ValueError:
        return dt.date.fromtimestamp(caminho.stat().st_mtime)
