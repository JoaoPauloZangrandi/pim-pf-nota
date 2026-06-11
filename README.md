# pim-pf-nota

Esteira **totalmente automatizada** que, a partir da divulgação da **PIM-PF — Pesquisa
Industrial Mensal / Produção Física** (IBGE, via API SIDRA), produz uma **nota informativa em
PDF** (gerada por LaTeX) e um **relatório HTML explicativo**, prontos para envio a clientes de
uma consultoria de macroeconomia.

> **Critério central do projeto: robustez.** A esteira nunca falha silenciosamente nem gera um
> PDF "silenciosamente errado". Em qualquer execução ela **produz um PDF válido** ou **falha com
> uma mensagem acionável e log**. A arquitetura de tratamento de erro segue o **Capítulo 7 de
> _Código Limpo_ (Robert C. Martin)** — cada decisão de design é rastreável a um dos princípios,
> e isso é documentado no relatório HTML.

---

## Status

🚧 **Marco 0 — esqueleto.** A estrutura de pastas, o empacotamento (`pyproject.toml`) e o
repositório estão prontos. Os módulos contêm apenas docstrings de placeholder; a implementação
segue as etapas descritas em [Roteiro de implementação](#roteiro-de-implementação).

---

## Arquitetura

```
src/pim_report/
├── config.py          # códigos de tabela, variáveis, períodos, caminhos, constantes
├── exceptions.py      # hierarquia de exceções de domínio
├── special_cases.py   # PeriodoNaoPublicado e afins (Special Case pattern)
├── sidra_client.py    # WRAPPER da API: traduz erros de terceiros -> exceções de domínio
├── schema.py          # validação pandera do DataFrame cru
├── transform.py       # as 4 leituras + categorias econômicas + seções/atividades
├── analysis.py        # narrativa determinística (manchete, destaques)
├── charts.py          # figuras (PDF p/ LaTeX, SVG/PNG p/ HTML)
├── render_latex.py    # Jinja2 -> .tex -> compila -> PDF (build determinístico)
├── render_html.py     # Jinja2 -> relatório HTML explicativo
├── cache.py           # persistência dos JSONs crus + modo de degradação
├── pipeline.py        # orquestra tudo (try/except/finally no topo)
└── __main__.py        # CLI: python -m pim_report --periodo last
```

---

## Requisitos

- **Python 3.11+** (desenvolvido/validado em 3.14).
- **Distribuição TeX** com `latexmk` no PATH. Este projeto foi configurado com
  **MiKTeX 24.1 + latexmk 4.88** no Windows. (`tectonic` é suportado como alternativa, se
  disponível.)

---

## Setup

```powershell
# 1. Criar e ativar o ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar o projeto em modo editável com as dependências de desenvolvimento
pip install -e ".[dev]"
```

No Linux/macOS, ative com `source .venv/bin/activate`.

---

## Como rodar

```powershell
# Gera a nota do período mais recente publicado
python -m pim_report --periodo last

# Reprocessa um mês específico a partir do cache
python -m pim_report --periodo 202504
```

Saídas em `output/`: `nota_pim_AAAA-MM.pdf`, o `.tex` preenchido e `relatorio.html`.

### Atalhos (Makefile)

```bash
make report   # gera a nota (--periodo last)
make test     # roda a suíte pytest
make lint     # ruff + black --check
```

> No Windows sem `make`, use os comandos equivalentes:
> `python -m pim_report --periodo last`, `pytest`, `ruff check . && black --check .`.

---

## Roteiro de implementação

| Etapa | Conteúdo |
|------:|----------|
| 0 | Esqueleto + exceções + testes que forçam erro (TDD, vermelho primeiro) |
| 1 | Wrapper SIDRA: timeout, retry (tenacity), tradução de erros |
| 2 | Validação de schema (pandera) + cache / modo de degradação |
| 3 | Transformação (4 leituras, categorias) + análise (narrativa) |
| 4 | Gráficos (PDF p/ LaTeX, SVG/PNG p/ HTML) |
| 5 | Render LaTeX → PDF (build determinístico) |
| 6 | Relatório HTML explicativo (mapeia os 8 princípios do Martin) |
| 7 | Orquestração (`pipeline.py`, `__main__.py`) |
| 8 | CI/cron (GitHub Actions), README final, smoke test e2e |

---

## Fonte dos dados

IBGE — Pesquisa Industrial Mensal / Produção Física (PIM-PF Brasil), via **API SIDRA**.
Os códigos de tabela/variáveis ficam centralizados em `src/pim_report/config.py`.
