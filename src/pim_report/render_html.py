"""render_html.py — relatório HTML explicativo e autossuficiente.

Gera ``output/relatorio.html`` com CSS inline e imagens embutidas em base64 (não depende de
arquivos externos). É um "notebook narrado": explica cada módulo, mapeia os 8 princípios do
Cap.7 do Martin ao código, mostra os números/gráficos e descreve a robustez.
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


# Mapa explícito: princípio do Martin Cap.7 -> onde foi aplicado (para o relatório).
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
        "trecho": "class SidraError(PimReportError): ...\n" "class SidraHTTPError(SidraError): ...",
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
        "Jinja2 -> .tex -> latexmk -> PDF, com runner injetável e tratamento de falha.",
    ),
    ("render_html.py", "Este relatório explicativo, autossuficiente."),
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


# =========================================================================== #
# Dossiê — documento único que explica TODO o projeto (Tutorial 5)
# =========================================================================== #
REPO_URL = "https://github.com/JoaoPauloZangrandi/pim-pf-nota"

# Mapa: exigência do enunciado -> como foi atendida -> onde no código.
REQUISITOS = [
    {
        "req": "Nota informativa para clientes — visualmente limpa, informativa e sucinta "
        "(1 página)",
        "como": "PDF de 1 página com manchete, quadro das 4 leituras, seções, 2 gráficos, "
        "destaques de atividades e parágrafo de contexto.",
        "onde": "transform.py · analysis.py · charts.py · render_latex.py · templates/nota.tex.j2",
    },
    {
        "req": "Automatizado: coleta + tratamento + análise num só processo",
        "como": "Um único comando (python -m pim_report --periodo last) executa a esteira de "
        "ponta a ponta, sem intervenção manual.",
        "onde": "pipeline.gerar_nota · __main__.py · sidra_client.py",
    },
    {
        "req": "Documento final em PDF, gerado em LaTeX (padrão interno da consultoria)",
        "como": "Template Jinja2 (.tex.j2) → .tex preenchido → compilação determinística. Toda a "
        "nota é LaTeX, como a consultoria usa internamente.",
        "onde": "render_latex.py · templates/nota.tex.j2",
    },
    {
        "req": "Divulgação ~09h, nota até 10h — cronograma apertado",
        "como": "Workflow agendado (cron) dispara logo após a divulgação; a esteira roda em "
        "segundos e publica os artefatos automaticamente.",
        "onde": ".github/workflows/divulgacao.yml",
    },
    {
        "req": "Minimizar o risco de o código não funcionar no dia",
        "como": "Timeout + retry, validação de schema, checagem de publicação, cache/degradação, "
        "testes que forçam erro, CI e abertura automática de issue em falha.",
        "onde": "sidra_client.py · schema.py · cache.py · pipeline.py · tests/ · workflows/",
    },
    {
        "req": "Decidir o que a nota deve conter (conteúdo mínimo da PIM-PF)",
        "como": "4 leituras padrão, grandes categorias econômicas, seções (extrativa × "
        "transformação), destaques de atividades, gráficos e fonte/rodapé.",
        "onde": "transform.py · analysis.py · templates/*",
    },
]

LINKS = [
    (
        "PIM-PF — página oficial (metodologia e calendário)",
        "https://www.ibge.gov.br/estatisticas/economicas/industria/9294-pesquisa-industrial-mensal-producao-fisica-brasil.html",
    ),
    ("SIDRA — PIM-PF Brasil", "https://sidra.ibge.gov.br/home/pimpfbr/brasil"),
    ("API SIDRA", "https://apisidra.ibge.gov.br/"),
    (
        "Exemplo de narrativa/contextualização (matéria do IBGE)",
        "https://agenciadenoticias.ibge.gov.br/agencia-noticias/2012-agencia-de-noticias/noticias/27576-pandemia-faz-producao-industrial-cair-9-1-e-ter-pior-marco-desde-2002",
    ),
    (
        "Metadados oficiais — tabela 8888",
        "https://servicodados.ibge.gov.br/api/v3/agregados/8888/metadados",
    ),
    ("Repositório do projeto (GitHub)", REPO_URL),
]

TRECHOS = [
    {
        "titulo": "Orquestração: try/except/finally no topo + degradação para cache (pipeline.py)",
        "codigo": (
            "try:\n"
            "    try:\n"
            "        pacote, alvo = ... coletar ao vivo ...\n"
            "        salvar_bruto(pacote, ...)            # grava o JSON cru de cada execução\n"
            "    except SidraError as erro:               # API caiu?\n"
            "        cache = carregar_mais_recente(...)   # usa o cache mais recente\n"
            "        pacote, de_cache = cache.registros, True\n"
            "    dados = construir_dados(pacote, ...)\n"
            "    narrativa = gerar_narrativa(dados)\n"
            "    pdf  = renderizar_nota(dados, narrativa, graficos, ...)\n"
            "    html = renderizar_relatorio(dados, narrativa, graficos, ...)\n"
            "except PimReportError as erro:\n"
            "    logger.error('Esteira falhou: %s', erro, exc_info=True); raise\n"
            "finally:\n"
            "    logger.info('=== Fim da esteira PIM-PF ===')"
        ),
    },
    {
        "titulo": "Retentativa só em erros transitórios — backoff exponencial (sidra_client.py)",
        "codigo": (
            "def _e_transitorio(exc):\n"
            "    if isinstance(exc, SidraConnectionError): return True\n"
            "    if isinstance(exc, SidraHTTPError):       return exc.transitorio  # 5xx\n"
            "    return False\n\n"
            "Retrying(stop=stop_after_attempt(self.max_tentativas),\n"
            "         wait=wait_exponential(multiplier=self.espera_inicial, max=...),\n"
            "         retry=retry_if_exception(_e_transitorio), reraise=True)"
        ),
    },
    {
        "titulo": "Compilação determinística com fallback latexmk → pdflatex (render_latex.py)",
        "codigo": (
            "for cmd in _comandos_candidatos(destino, caminho_tex):  # latexmk, depois pdflatex\n"
            "    resultado = executar(cmd, cwd=str(destino))\n"
            "    if resultado.returncode == 0 and caminho_pdf.exists():\n"
            "        return caminho_pdf\n"
            "# todos falharam: preserva o .log e levanta erro acionável\n"
            "raise LatexCompilationError(..., log_path=str(caminho_log), contexto={...})"
        ),
    },
    {
        "titulo": "Jinja2 para LaTeX: delimitadores que não colidem com as chaves do TeX",
        "codigo": (
            "Environment(block_start_string='((*', block_end_string='*))',\n"
            "            variable_start_string='(((', variable_end_string=')))',\n"
            "            autoescape=False, undefined=StrictUndefined)\n"
            "# no template: ((* for s in dados.secoes *)) ((( s.nome|tex ))) & "
            "((( s.var_mensal|pct|tex )))"
        ),
    },
    {
        "titulo": "Special Case: mês ainda não publicado (special_cases.py / pipeline.py)",
        "codigo": (
            "if periodo != 'last' and periodo > recente:\n"
            "    snp = PeriodoNaoPublicado(periodo, recente, hoje)\n"
            "    return Execucao(False, periodo, None, None, False, snp.mensagem())\n"
            "# -> não gera PDF com mês velho fingindo ser novo"
        ),
    },
]


def renderizar_dossie(
    dados: DadosPim,
    narrativa: Narrativa,
    graficos: Graficos,
    *,
    dir_saida: Path = config.DIR_OUTPUT,
    dir_templates: Path = config.DIR_TEMPLATES,
    pdf_path: Path | None = None,
) -> Path:
    """Renderiza ``output/dossie.html`` — documento único que explica TODO o projeto."""
    exigir_nao_nulo(dados, "dados", operacao="renderizar_dossie")
    exigir_nao_nulo(narrativa, "narrativa", operacao="renderizar_dossie")
    exigir_nao_nulo(graficos, "graficos", operacao="renderizar_dossie")

    env = Environment(
        loader=FileSystemLoader(str(dir_templates)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["pct"] = formatar_pct

    try:
        template = env.get_template("dossie.html.j2")
        html = template.render(
            dados=dados,
            narrativa=narrativa,
            img_serie=_data_uri_png(graficos.serie_png),
            img_categorias=_data_uri_png(graficos.categorias_png),
            requisitos=REQUISITOS,
            principios=PRINCIPIOS,
            modulos=MODULOS,
            links=LINKS,
            trechos=TRECHOS,
            repo_url=REPO_URL,
            pdf_nome=pdf_path.name if pdf_path else "",
        )
    except Exception as erro:
        raise HtmlRenderError(
            "Falha ao renderizar o dossiê HTML",
            contexto={"dir_templates": str(dir_templates)},
        ) from erro

    dir_saida.mkdir(parents=True, exist_ok=True)
    caminho = dir_saida / "dossie.html"
    caminho.write_text(html, encoding="utf-8")
    logger.info("Dossiê HTML gerado: %s", caminho)
    return caminho


# =========================================================================== #
# Guia didático — passo a passo cronológico de uma execução
# =========================================================================== #
# Cada passo: o que acontece, qual arquivo/função faz, e onde está a robustez.
PASSOS = [
    {
        "n": 0,
        "titulo": "O gatilho — você (ou o robô) dispara um comando",
        "arquivo": "__main__.py",
        "funcao": "main() → _parse() → _configurar_logging()",
        "oque": "Tudo começa com 'python -m pim_report --periodo last'. O __main__ lê o argumento "
        "--periodo ('last' = mês mais recente, ou AAAAMM), liga o logging (arquivo + console) e "
        "chama o pipeline. No dia da divulgação, quem digita o comando é o cron do GitHub Actions.",
        "robustez": "Entrypoint único e idempotente; logging ativo desde o primeiro instante, "
        "gravando em output/pim_report.log.",
    },
    {
        "n": 1,
        "titulo": "A batuta da orquestra",
        "arquivo": "pipeline.py",
        "funcao": "gerar_nota()",
        "oque": "É o maestro: chama, em ordem, coleta → cache → validação → transformação → "
        "narrativa → gráficos → PDF → HTML. Toda a sequência vive dentro de um try/except/finally.",
        "robustez": "O try/except/finally foi escrito ANTES da lógica feliz (Martin, princípio 2). "
        "O except captura PimReportError, registra com stack trace e re-levanta; o finally sempre "
        "loga o fim — nada termina em silêncio.",
    },
    {
        "n": 2,
        "titulo": "Perguntar ao IBGE qual é o mês mais recente",
        "arquivo": "sidra_client.py  (+ pipeline._ultimo_periodo_disponivel)",
        "funcao": "SidraClient.buscar_tabela(periodo='last')",
        "oque": "Monta a URL da API e faz um GET. A URL /values/t/8888/n1/all/v/.../p/last/c544/all "
        "significa: tabela 8888, nível Brasil, variáveis pedidas, último período, classificação 544 "
        "(seções/atividades), todas as categorias. A resposta é uma lista JSON cujo 1º item é o "
        "cabeçalho de rótulos.",
        "robustez": "Timeout explícito em toda requisição; tenacity re-tenta com backoff exponencial "
        "SÓ erros transitórios (conexão/timeout e HTTP 5xx). Timeout→SidraConnectionError, "
        "5xx→SidraHTTPError, JSON inválido→SidraPayloadError, vazio→SidraEmptyError. Nenhum erro de "
        "'requests' vaza para fora do wrapper.",
    },
    {
        "n": 3,
        "titulo": "Esse mês já saiu? (o caso especial)",
        "arquivo": "pipeline.py  +  special_cases.py",
        "funcao": "PeriodoNaoPublicado",
        "oque": "Se você pediu um mês específico que ainda não foi divulgado (pedido > mais recente), "
        "a esteira NÃO inventa nem usa mês velho: devolve o objeto PeriodoNaoPublicado, loga o aviso "
        "e encerra com código 2, sem gerar PDF.",
        "robustez": "Special Case pattern (Fowler / Martin princípio 6): o caso 'não publicado' é um "
        "objeto explícito, não um None nem um if espalhado. O caminho feliz fica limpo.",
    },
    {
        "n": 4,
        "titulo": "Coletar os três conjuntos de dados",
        "arquivo": "pipeline.py",
        "funcao": "coletar_pacote()",
        "oque": "Faz 3 consultas: (a) ATIVIDADES — tabela 8888, último mês, todas as categorias, as 5 "
        "variáveis (4 leituras + índice dessazonalizado); (b) SÉRIE — tabela 8888, indústria geral, só "
        "o índice dessazonalizado, nos últimos 36 meses (para o gráfico de linha); (c) CATEGORIAS — "
        "tabela 8887, grandes categorias econômicas, as 4 leituras. Junta tudo num 'pacote' (dict).",
        "robustez": "Cada consulta passa pelo mesmo wrapper robusto do passo 2.",
    },
    {
        "n": 5,
        "titulo": "Guardar uma cópia crua (a rede de segurança)",
        "arquivo": "cache.py",
        "funcao": "salvar_bruto()  /  carregar_mais_recente()",
        "oque": "O pacote cru é gravado em data/raw/AAAA-MM-DD.json a cada execução.",
        "robustez": "É a peça-chave do MODO DE DEGRADAÇÃO: se a API estiver fora do ar, o pipeline "
        "chama carregar_mais_recente(), usa o cache mais recente e marca de_cache=True (que vira um "
        "aviso destacado no PDF/HTML). Se nem cache existir, levanta CacheVazioError — falha clara, "
        "não um PDF vazio.",
    },
    {
        "n": 6,
        "titulo": "Conferir se o formato é o esperado (falhar cedo)",
        "arquivo": "schema.py",
        "funcao": "validar_bruto()  (chamada dentro de transform.montar_dataframe)",
        "oque": "Antes de calcular qualquer coisa, o pandera confere se as colunas (V, D2C, D3C, D4C…) "
        "existem e têm o tipo certo.",
        "robustez": "Se o IBGE mudar o layout, a esteira para AQUI com SchemaValidationError (dizendo "
        "qual coluna sumiu) — em vez de gerar números errados silenciosamente.",
    },
    {
        "n": 7,
        "titulo": "Transformar texto em números e leituras",
        "arquivo": "transform.py",
        "funcao": "construir_dados() → montar_dataframe(), _item_de(), _destaques(), _serie_dessaz()",
        "oque": "Descarta a linha de cabeçalho, converte o campo V (texto, ex. '0,7') em número, "
        "tratando ausências ('...', '-') como NaN. Depois filtra por variável/categoria/período para "
        "montar: as 4 leituras da indústria geral, as seções (extrativa × transformação), as grandes "
        "categorias econômicas, as maiores altas/baixas entre atividades e a série de 36 meses.",
        "robustez": "Ausência de dado vira NaN (um float), nunca None (princípios 1, 7, 8). Categoria "
        "faltando no período → TransformError com contexto.",
    },
    {
        "n": 8,
        "titulo": "Escrever a história por trás do número",
        "arquivo": "analysis.py",
        "funcao": "gerar_narrativa()",
        "oque": "Gera manchete, subtítulo, parágrafo de contexto e os textos de destaques. Tudo por "
        "REGRAS FIXAS sobre os sinais e as magnitudes (ex.: alta no mês + queda em 12 meses → frase de "
        "'recuperação sobre base fraca'). É determinístico: mesmos dados → mesmo texto, sem invenção.",
        "robustez": "Não gera narrativa para um resultado não publicado (checa .publicado).",
    },
    {
        "n": 9,
        "titulo": "Desenhar os gráficos",
        "arquivo": "charts.py",
        "funcao": "gerar_graficos()",
        "oque": "Cria 2 figuras com matplotlib: a linha do índice dessazonalizado (36 meses) e as "
        "barras de variação mensal das categorias (verde = alta, vermelho = queda). Salva cada uma em "
        "PDF (vetorial, para o LaTeX) e PNG (para embutir nos HTML).",
        "robustez": "Backend 'Agg' (sem tela) — funciona em servidor/CI sem ambiente gráfico.",
    },
    {
        "n": 10,
        "titulo": "Montar e compilar o PDF em LaTeX",
        "arquivo": "render_latex.py  +  templates/nota.tex.j2",
        "funcao": "renderizar_nota() → compilar_pdf()",
        "oque": "O Jinja2 preenche o template .tex com os dados/gráficos (usando delimitadores "
        "((* *)) e ((( ))) para não brigar com as chaves do LaTeX; o % é escapado). Em seguida compila "
        "o .tex em PDF via subprocess.",
        "robustez": "Build determinístico com FALLBACK: tenta latexmk e, se falhar (ex.: MiKTeX sem "
        "Perl), usa pdflatex. Captura stdout/stderr e o .log; se nenhum compilador gerar o PDF, "
        "levanta LatexCompilationError preservando o log — nunca um PDF parcial.",
    },
    {
        "n": 11,
        "titulo": "Gerar os HTML e encerrar com um veredito",
        "arquivo": "render_html.py  +  pipeline.py  +  __main__.py",
        "funcao": "renderizar_relatorio/dossie/guia; finally; main() retorna 0/1/2",
        "oque": "Gera o relatório técnico, o dossiê e este guia (todos autossuficientes). O finally do "
        "pipeline loga o fim; o __main__ imprime o resultado e devolve um código de saída: 0 = nota "
        "gerada, 2 = mês não publicado, 1 = falha de domínio (com mensagem acionável e log).",
        "robustez": "O invariante final: ou um PDF válido, ou falha clara com log — jamais um PDF "
        "silenciosamente errado.",
    },
]

GLOSSARIO = [
    (
        "Número-índice (base 2022=100)",
        "A produção não é medida em 'toneladas', e sim como um índice: 100 = média de 2022. Um índice "
        "de 106 significa produzir 6% a mais que a média de 2022.",
    ),
    (
        "Ajuste sazonal (dessazonalizado)",
        "Remove padrões que se repetem todo ano (férias, festas, safra). Sem isso, dezembro sempre "
        "pareceria 'alto'. Com ajuste, dá para comparar um mês com o anterior de forma justa.",
    ),
    (
        "Variação mensal m/m-1 (a 'margem')",
        "Quanto a produção cresceu/caiu ante o mês imediatamente anterior, já dessazonalizada. É o "
        "termômetro do momento — mostra a aceleração ou desaceleração mais recente.",
    ),
    (
        "Variação interanual m/m-12",
        "Compara o mês com o MESMO mês do ano passado (ex.: abr/2026 vs abr/2025). Mostra o quadro "
        "anual, menos sensível a ruído de um mês isolado.",
    ),
    (
        "Acumulado no ano",
        "Soma do ano até o mês, comparada com o mesmo período do ano anterior. Responde: 'como está "
        "o ano até agora?'",
    ),
    (
        "Acumulado em 12 meses",
        "Janela móvel dos últimos 12 meses vs os 12 anteriores. É a medida de TENDÊNCIA mais estável.",
    ),
    (
        "Grandes categorias econômicas",
        "Agrupa a indústria por destino do produto: bens de capital (máquinas/equipamentos = "
        "investimento), bens intermediários (insumos para outras indústrias), bens de consumo duráveis "
        "(carros, eletrodomésticos) e semi/não duráveis (alimentos, roupas).",
    ),
    (
        "Seções: extrativa × transformação",
        "Extrativa = tirar da natureza (petróleo, minério). Transformação = manufatura (alimentos, "
        "química, veículos…). Juntas formam a 'indústria geral'.",
    ),
]


def renderizar_guia(
    dados: DadosPim,
    narrativa: Narrativa,
    graficos: Graficos,
    *,
    dir_saida: Path = config.DIR_OUTPUT,
    dir_templates: Path = config.DIR_TEMPLATES,
    pdf_path: Path | None = None,
) -> Path:
    """Renderiza ``output/guia.html`` — passo a passo didático e cronológico da esteira."""
    exigir_nao_nulo(dados, "dados", operacao="renderizar_guia")
    exigir_nao_nulo(narrativa, "narrativa", operacao="renderizar_guia")
    exigir_nao_nulo(graficos, "graficos", operacao="renderizar_guia")

    env = Environment(
        loader=FileSystemLoader(str(dir_templates)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["pct"] = formatar_pct

    try:
        template = env.get_template("guia.html.j2")
        html = template.render(
            dados=dados,
            narrativa=narrativa,
            img_serie=_data_uri_png(graficos.serie_png),
            img_categorias=_data_uri_png(graficos.categorias_png),
            passos=PASSOS,
            glossario=GLOSSARIO,
            repo_url=REPO_URL,
            pdf_nome=pdf_path.name if pdf_path else "",
        )
    except Exception as erro:
        raise HtmlRenderError(
            "Falha ao renderizar o guia HTML",
            contexto={"dir_templates": str(dir_templates)},
        ) from erro

    dir_saida.mkdir(parents=True, exist_ok=True)
    caminho = dir_saida / "guia.html"
    caminho.write_text(html, encoding="utf-8")
    logger.info("Guia HTML gerado: %s", caminho)
    return caminho
