"""sidra_client.py — WRAPPER da API SIDRA (isolamento de dependência de terceiros).

Traduz erros de `sidrapy`/`requests` (Timeout, HTTPError, JSONDecodeError, 5xx, vazio) para
UMA família de exceções de domínio (Martin Cap.7 princípio 5). Aplica timeout explícito e
retentativas com backoff exponencial (tenacity) apenas em erros transitórios. Inclui caminho
de fallback via `requests` direto na API.

A ser implementado na Etapa 1.
"""

# Placeholder — implementação na Etapa 1.
