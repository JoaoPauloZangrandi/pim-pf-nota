"""exceptions.py — hierarquia de exceções de domínio da esteira PIM-PF.

Este módulo materializa vários princípios do Capítulo 7 de *Código Limpo* (R. C. Martin):

- **Princípio 1 — Use exceções, não códigos de retorno.** Nenhuma função do pacote sinaliza
  erro via ``None``/``-1``/flag; toda falha vira uma exceção desta família.
- **Princípio 3 — Use exceções "não verificadas" + hierarquia própria.** Python não obriga o
  chamador a declarar exceções; aqui definimos uma hierarquia de domínio com uma raiz única
  (:class:`PimReportError`), permitindo capturar de forma ampla (``except PimReportError``) ou
  cirúrgica (``except SidraHTTPError``).
- **Princípio 4 — Forneça contexto nas exceções.** A base aceita um dicionário ``contexto`` e
  embute "operação que falhou + dados relevantes" na mensagem. O encadeamento
  (``raise ... from e``) é feito por quem traduz a causa de terceiros.
- **Princípio 5 — Defina classes segundo a necessidade do chamador.** A família :class:`SidraError`
  existe para o chamador do cliente SIDRA tratar de forma única os erros vindos de ``requests``/
  ``sidrapy`` (timeout, 5xx, JSON inválido, vazio), isolando a dependência de terceiros.
- **Princípio 8 — Não passe None.** :func:`exigir_nao_nulo` valida parâmetros na fronteira dos
  módulos e levanta :class:`InvalidParameterError` quando um obrigatório vem ``None``.
"""

from __future__ import annotations

from typing import Any


class PimReportError(Exception):
    """Raiz de toda exceção de domínio da esteira PIM-PF (Martin, princípios 1 e 3).

    Carrega uma mensagem informativa e um ``contexto`` opcional (princípio 4), de modo que o
    ``__str__`` sempre descreva *o que* falhou e *com quais dados*.
    """

    def __init__(self, mensagem: str, *, contexto: dict[str, Any] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.contexto: dict[str, Any] = dict(contexto) if contexto else {}

    def __str__(self) -> str:
        if not self.contexto:
            return self.mensagem
        partes = ", ".join(f"{chave}={valor!r}" for chave, valor in self.contexto.items())
        return f"{self.mensagem} [{partes}]"


# ---------------------------------------------------------------------------
# Validação de parâmetros (princípio 8 — não passe None)
# ---------------------------------------------------------------------------
class InvalidParameterError(PimReportError):
    """Parâmetro inválido na fronteira de um módulo (ex.: obrigatório recebido como ``None``)."""


def exigir_nao_nulo(valor: Any, nome: str, *, operacao: str | None = None) -> Any:
    """Garante que ``valor`` não é ``None``; do contrário levanta :class:`InvalidParameterError`.

    Martin, princípio 8 (não passe None): valide na fronteira e proíba ``None`` por padrão.
    Retorna o próprio valor para permitir uso encadeado (``x = exigir_nao_nulo(x, "x")``).
    """
    if valor is None:
        contexto: dict[str, Any] = {"parametro": nome}
        if operacao is not None:
            contexto["operacao"] = operacao
        raise InvalidParameterError(
            f"Parâmetro obrigatório ausente: {nome!r} não pode ser None.",
            contexto=contexto,
        )
    return valor


# ---------------------------------------------------------------------------
# Família SIDRA (princípio 5 — wrapper isola a dependência de terceiros)
# ---------------------------------------------------------------------------
class SidraError(PimReportError):
    """Falha ao obter dados da API SIDRA. Raiz da família traduzida pelo cliente.

    O chamador pode tratar toda a categoria com ``except SidraError`` sem conhecer
    ``requests``/``sidrapy`` — o que permite trocar a biblioteca de terceiros sem afetar o
    resto do código.
    """


class SidraConnectionError(SidraError):
    """Erro transitório de rede: timeout ou falha de conexão. Candidato a retentativa."""


class SidraHTTPError(SidraError):
    """A API respondeu com status HTTP de erro (4xx/5xx). 5xx é transitório (retentável)."""

    def __init__(
        self,
        mensagem: str,
        *,
        status_code: int | None = None,
        contexto: dict[str, Any] | None = None,
    ) -> None:
        contexto = dict(contexto) if contexto else {}
        if status_code is not None:
            contexto.setdefault("status_code", status_code)
        super().__init__(mensagem, contexto=contexto)
        self.status_code = status_code

    @property
    def transitorio(self) -> bool:
        """``True`` para 5xx (servidor) — erros que justificam retentativa."""
        return self.status_code is not None and 500 <= self.status_code < 600


class SidraPayloadError(SidraError):
    """A resposta veio mas é inválida: JSON malformado ou estrutura inesperada."""


class SidraEmptyError(SidraError):
    """A consulta foi bem-sucedida porém não retornou registros de dados."""


# ---------------------------------------------------------------------------
# Validação de schema (Etapa 2)
# ---------------------------------------------------------------------------
class SchemaValidationError(PimReportError):
    """O DataFrame cru não corresponde ao schema esperado (IBGE pode ter mudado o layout)."""


# ---------------------------------------------------------------------------
# Transformação e análise (Etapa 3)
# ---------------------------------------------------------------------------
class TransformError(PimReportError):
    """Falha ao transformar os dados crus nas leituras/categorias da PIM-PF."""


class AnalysisError(PimReportError):
    """Falha ao derivar a narrativa determinística a partir dos dados."""


# ---------------------------------------------------------------------------
# Cache e modo de degradação (Etapa 2)
# ---------------------------------------------------------------------------
class CacheError(PimReportError):
    """Falha ao ler/gravar o cache de respostas cruas."""


class CacheVazioError(CacheError):
    """Não há cache disponível para o modo de degradação (API fora + cache inexistente)."""


# ---------------------------------------------------------------------------
# Renderização (Etapas 5 e 6)
# ---------------------------------------------------------------------------
class RenderError(PimReportError):
    """Raiz das falhas de renderização (LaTeX/HTML)."""


class LatexCompilationError(RenderError):
    """A compilação LaTeX falhou. Carrega o caminho do ``.log`` capturado, quando houver."""

    def __init__(
        self,
        mensagem: str,
        *,
        log_path: str | None = None,
        contexto: dict[str, Any] | None = None,
    ) -> None:
        contexto = dict(contexto) if contexto else {}
        if log_path is not None:
            contexto.setdefault("log_path", log_path)
        super().__init__(mensagem, contexto=contexto)
        self.log_path = log_path


class HtmlRenderError(RenderError):
    """Falha ao renderizar o relatório HTML."""
