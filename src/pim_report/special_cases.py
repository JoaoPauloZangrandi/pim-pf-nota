"""special_cases.py — objetos Special Case (padrão de Fowler; Martin Cap.7).

- **Princípio 6 — Defina o fluxo normal (Special Case pattern).** O caso "mês ainda não
  publicado" não é um erro nem um ``None``: é um *resultado legítimo porém especial*. Em vez de
  espalhar ``if dados is None`` pelo código, devolvemos um objeto :class:`PeriodoNaoPublicado`
  que compartilha a interface do resultado normal (atributo ``publicado``). O caminho feliz
  fica limpo; o pipeline apenas checa ``resultado.publicado``.
- **Princípio 7 — Não retorne None.** Quem detecta "ainda não saiu" retorna este objeto.
- **Princípio 8 — Não passe None.** O construtor valida seus campos com
  :func:`exigir_nao_nulo`.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import ClassVar, Protocol, runtime_checkable

from .exceptions import exigir_nao_nulo


@runtime_checkable
class ResultadoPeriodo(Protocol):
    """Interface comum entre o resultado normal e o Special Case.

    Ambos expõem ``publicado``; assim o chamador trata os dois de forma uniforme, sem
    precisar checar contra ``None`` (Special Case pattern). O resultado "feliz" com os dados
    da PIM-PF (a ser definido na Etapa 3) terá ``publicado = True``.
    """

    publicado: bool


@dataclass(frozen=True)
class PeriodoNaoPublicado:
    """Special Case: a PIM-PF do período solicitado ainda não foi divulgada no SIDRA.

    Substitui um ``None``/flag de erro. O pipeline checa ``.publicado`` (sempre ``False``) e
    encerra com aviso claro, **sem** gerar uma nota com mês velho fingindo ser novo.

    Attributes:
        periodo_solicitado: período pedido, no formato ``AAAAMM`` (ex.: ``"202505"``).
        periodo_disponivel: período mais recente efetivamente disponível (``AAAAMM``).
        data_consulta: data em que a consulta foi feita.
    """

    periodo_solicitado: str
    periodo_disponivel: str
    data_consulta: _dt.date

    publicado: ClassVar[bool] = False

    def __post_init__(self) -> None:
        exigir_nao_nulo(
            self.periodo_solicitado, "periodo_solicitado", operacao="PeriodoNaoPublicado"
        )
        exigir_nao_nulo(
            self.periodo_disponivel, "periodo_disponivel", operacao="PeriodoNaoPublicado"
        )
        exigir_nao_nulo(self.data_consulta, "data_consulta", operacao="PeriodoNaoPublicado")

    def mensagem(self) -> str:
        """Aviso acionável, pronto para log e para a saída da CLI."""
        return (
            f"PIM-PF do período {self.periodo_solicitado} ainda não publicada no SIDRA "
            f"(mais recente disponível: {self.periodo_disponivel}; "
            f"consulta em {self.data_consulta:%d/%m/%Y}). Nenhuma nota foi gerada."
        )
