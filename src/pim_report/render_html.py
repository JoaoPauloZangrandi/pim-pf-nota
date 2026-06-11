"""render_html.py — relatório HTML explicativo e autossuficiente.

Gera ``output/relatorio.html`` com CSS inline e imagens embutidas em base64 (não depende de
arquivos externos). É um "notebook narrado": explica cada módulo, mapeia os 8 princípios do
Cap.7 do Martin ao código, mostra os números/gráficos e descreve a robustez.

As constantes PRINCIPIOS e MODULOS são reaproveitadas pelo documento PDF completo
(``render_latex.renderizar_manual``).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from .analysis import Narrativa, formatar_pct
from .charts import Graficos
from .exceptions import HtmlRenderError, exigir_nao_nulo
from .transform import DadosPim

logger = logging.getLogger(__name__)


def _data_uri_png(caminho: Path) -> str:
    dados = base64.b64encode(Path(caminho).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{dados}"


# Mapa explícito: princípio do Martin Cap.7 -> onde foi aplicado.
PRINCIPIOS = [
    {
        "n": 1,
        "titulo": "Use exceções, não códigos de retorno",
        "onde": "Toda falha levanta exceção; nenhuma função sinaliza erro com None/-1/flag.",
        "trecho": "raise SidraEmptyError('Consulta ao SIDRA sem registros de dados', ...)",
        "arquivo": "sidra_client.py, transform.py, render_latex.py",
    },
    {
        "n": 2,
        "titulo": "Escreva try/except/finally primeiro (TDD)",
        "onde": "Os testes que forçam exceção (Etapa 0) vieram antes da lógica feliz; o "
        "pipeline foi escrito ao redor de um try/except/finally.",
        "trecho": "def test_timeout_e_traduzido_para_sidra_connection_error(...): "
        "with pytest.raises(SidraConnectionError): ...",
        "arquivo": "tests/test_sidra_client.py, tests/test_render.py, pipeline.py",
    },
    {
        "n": 3,
        "titulo": "Exceções não verificadas + hierarquia de domínio",
        "onde": "Hierarquia própria sob uma raiz única PimReportError; o chamador captura "
        "amplo (PimReportError) ou cirúrgico (SidraHTTPError).",
        "trecho": "class SidraError(PimReportError): ...\nclass SidraHTTPError(SidraError): ...",
        "arquivo": "exceptions.py",
    },
    {
        "n": 4,
        "titulo": "Forneça contexto nas exceções",
        "onde": "A base carrega um dicionário 'contexto' e embute na mensagem; o wrapper usa "
        "raise ... from e (encadeamento) e o render preserva o .log.",
        "trecho": "raise SidraConnectionError('Falha de conexão/timeout ...', "
        "contexto={'url': url, 'timeout': self.timeout}) from erro",
        "arquivo": "exceptions.py, sidra_client.py, render_latex.py",
    },
    {
        "n": 5,
        "titulo": "Defina classes segundo a necessidade do chamador",
        "onde": "O cliente SIDRA é um WRAPPER que traduz requests.Timeout/HTTPError/"
        "JSONDecodeError/5xx/vazio em UMA família SidraError, isolando a dependência.",
        "trecho": "except (requests.Timeout, requests.ConnectionError) as erro:\n"
        "    raise SidraConnectionError(...) from erro",
        "arquivo": "sidra_client.py, exceptions.py",
    },
    {
        "n": 6,
        "titulo": "Defina o fluxo normal (Special Case pattern)",
        "onde": "'Mês ainda não publicado' vira o objeto PeriodoNaoPublicado (publicado=False) "
        "em vez de if/else espalhado; o caminho feliz fica limpo.",
        "trecho": "@dataclass(frozen=True)\nclass PeriodoNaoPublicado:\n    publicado = False",
        "arquivo": "special_cases.py, pipeline.py",
    },
    {
        "n": 7,
        "titulo": "Não retorne None",
        "onde": "Sucesso devolve coleção/objeto concreto; ausência de cache vira CacheVazioError; "
        "valores numéricos ausentes viram NaN (float), não None.",
        "trecho": "if not arquivos: raise CacheVazioError(...)",
        "arquivo": "cache.py, transform.py, sidra_client.py",
    },
    {
        "n": 8,
        "titulo": "Não passe None",
        "onde": "Parâmetros obrigatórios são validados na fronteira dos módulos com "
        "exigir_nao_nulo(), que levanta InvalidParameterError.",
        "trecho": "exigir_nao_nulo(tabela, 'tabela', operacao='buscar_tabela')",
        "arquivo": "exceptions.py (guard) + todos os módulos",
    },
]

MODULOS = [
    (
        "config.py",
        "Centraliza códigos de tabela/variáveis/classificações do SIDRA, caminhos e "
        "parâmetros de rede. Troca de código = uma linha.",
    ),
    (
        "exceptions.py",
        "Hierarquia de exceções de domínio (raiz PimReportError) + guard "
        "exigir_nao_nulo. Princípios 1, 3, 4, 5, 8.",
    ),
    ("special_cases.py", "PeriodoNaoPublicado (Special Case de Fowler). Princípios 6 e 7."),
    (
        "sidra_client.py",
        "Wrapper da API: timeout, retry exponencial (tenacity) só em "
        "transitórios, e tradução de erros para SidraError. Princípio 5.",
    ),
    (
        "schema.py",
        "Validação pandera do DataFrame cru: falha cedo e clara se o IBGE mudar o layout.",
    ),
    ("cache.py", "Persiste o JSON cru e habilita o modo de degradação (usa o cache mais recente)."),
    ("transform.py", "As 4 leituras, categorias econômicas, seções e destaques + série dessaz."),
    ("analysis.py", "Narrativa determinística (manchete, contexto, destaques) derivada dos dados."),
    ("charts.py", "Figuras em PDF (LaTeX) e PNG (HTML), estilo limpo."),
    (
        "render_latex.py",
        "Jinja2 -> .tex -> latexmk/pdflatex -> PDF (nota + manual), com tratamento de falha.",
    ),
    ("render_html.py", "Relatório HTML explicativo, autossuficiente."),
    ("pipeline.py", "Orquestra tudo com try/except/finally no topo e logging por etapa."),
]


def renderizar_relatorio(
    dados: DadosPim,
    narrativa: Narrativa,
    graficos: Graficos,
    *,
    dir_saida: Path = config.DIR_OUTPUT,
    dir_templates: Path = config.DIR_TEMPLATES,
    pdf_path: Path | None = None,
) -> Path:
    """Renderiza o relatório HTML e devolve o caminho de ``relatorio.html``."""
    exigir_nao_nulo(dados, "dados", operacao="renderizar_relatorio")
    exigir_nao_nulo(narrativa, "narrativa", operacao="renderizar_relatorio")
    exigir_nao_nulo(graficos, "graficos", operacao="renderizar_relatorio")

    env = Environment(
        loader=FileSystemLoader(str(dir_templates)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["pct"] = formatar_pct

    try:
        template = env.get_template("relatorio.html.j2")
        html = template.render(
            dados=dados,
            narrativa=narrativa,
            img_serie=_data_uri_png(graficos.serie_png),
            img_categorias=_data_uri_png(graficos.categorias_png),
            principios=PRINCIPIOS,
            modulos=MODULOS,
            pdf_nome=pdf_path.name if pdf_path else "",
        )
    except Exception as erro:
        raise HtmlRenderError(
            "Falha ao renderizar o relatório HTML",
            contexto={"dir_templates": str(dir_templates)},
        ) from erro

    dir_saida.mkdir(parents=True, exist_ok=True)
    caminho = dir_saida / "relatorio.html"
    caminho.write_text(html, encoding="utf-8")
    logger.info("Relatório HTML gerado: %s", caminho)
    return caminho
