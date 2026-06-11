"""config.py — constantes centralizadas da esteira.

Único lugar onde vivem códigos de tabela SIDRA, variáveis, classificações, caminhos e
parâmetros de rede. Se o IBGE trocar um código, a alteração é de UMA linha aqui (Martin:
separação de preocupações; o resto do código nunca hardcoda um código de tabela).

Códigos confirmados nos metadados oficiais do IBGE (série nova da PIM-PF, base 2022=100):
- https://servicodados.ibge.gov.br/api/v3/agregados/8888/metadados
- https://servicodados.ibge.gov.br/api/v3/agregados/8887/metadados
Verificado em 2026-06.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Caminhos do projeto
# --------------------------------------------------------------------------- #
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DIR_DATA_RAW: Path = PROJECT_ROOT / "data" / "raw"
DIR_OUTPUT: Path = PROJECT_ROOT / "output"
DIR_TEMPLATES: Path = PROJECT_ROOT / "templates"

# --------------------------------------------------------------------------- #
# API SIDRA
# --------------------------------------------------------------------------- #
SIDRA_BASE_URL: str = "https://apisidra.ibge.gov.br"
SIDRA_NIVEL_TERRITORIAL: str = "n1"  # n1 = Brasil
SIDRA_TERRITORIO: str = "all"

# Tabelas da PIM-PF Brasil (série iniciada em 2023, base 2022=100)
TABELA_ATIVIDADES: str = "8888"  # por seções e atividades industriais (CNAE 2.0)
TABELA_CATEGORIAS: str = "8887"  # por grandes categorias econômicas

# Variáveis (idênticas nas duas tabelas)
VAR_INDICE: str = "12606"  # número-índice (2022=100)
VAR_INDICE_DESSAZ: str = "12607"  # número-índice com ajuste sazonal
VAR_VAR_MENSAL: str = "11601"  # variação m/m-1 (com ajuste sazonal)
VAR_INTERANUAL: str = "11602"  # variação m / mesmo mês do ano anterior
VAR_ACUM_ANO: str = "11603"  # acumulado no ano
VAR_ACUM_12M: str = "11604"  # acumulado em 12 meses

# As 4 leituras padrão da PIM-PF (rótulo legível -> código da variável)
LEITURAS: dict[str, str] = {
    "Variação mensal (m/m-1, com ajuste sazonal)": VAR_VAR_MENSAL,
    "Variação interanual (m/m-12)": VAR_INTERANUAL,
    "Acumulado no ano": VAR_ACUM_ANO,
    "Acumulado em 12 meses": VAR_ACUM_12M,
}

# Conjunto de variáveis pedido em cada requisição (4 leituras + índice dessazonalizado)
VARIAVEIS_PADRAO: tuple[str, ...] = (
    VAR_VAR_MENSAL,
    VAR_INTERANUAL,
    VAR_ACUM_ANO,
    VAR_ACUM_12M,
    VAR_INDICE_DESSAZ,
)

# Classificação 544 — seções e atividades industriais (tabela 8888)
CLASSIF_ATIVIDADES: str = "544"
CAT_INDUSTRIA_GERAL: str = "129314"
CAT_EXTRATIVA: str = "129315"
CAT_TRANSFORMACAO: str = "129316"
# "all" traz indústria geral + extrativa + transformação + todas as atividades detalhadas
CATEGORIAS_ATIVIDADES: str = "all"

# Classificação 543 — grandes categorias econômicas (tabela 8887)
CLASSIF_CATEGORIAS: str = "543"
CAT_BENS_CAPITAL: str = "129278"
CAT_BENS_INTERMEDIARIOS: str = "129283"
CAT_CONSUMO_DURAVEIS: str = "129301"
CAT_CONSUMO_SEMI_NAO_DURAVEIS: str = "129305"
GRANDES_CATEGORIAS: dict[str, str] = {
    "Bens de capital": CAT_BENS_CAPITAL,
    "Bens intermediários": CAT_BENS_INTERMEDIARIOS,
    "Bens de consumo duráveis": CAT_CONSUMO_DURAVEIS,
    "Bens de consumo semi e não duráveis": CAT_CONSUMO_SEMI_NAO_DURAVEIS,
}

# --------------------------------------------------------------------------- #
# Parâmetros de robustez (rede / retentativas)
# --------------------------------------------------------------------------- #
HTTP_TIMEOUT_SEGUNDOS: float = 30.0
MAX_TENTATIVAS: int = 4
ESPERA_INICIAL_SEGUNDOS: float = 2.0
ESPERA_MAXIMA_SEGUNDOS: float = 30.0

# --------------------------------------------------------------------------- #
# Metadados de fonte (rodapé da nota)
# --------------------------------------------------------------------------- #
FONTE: str = "IBGE — Pesquisa Industrial Mensal / Produção Física (PIM-PF Brasil), via SIDRA"
