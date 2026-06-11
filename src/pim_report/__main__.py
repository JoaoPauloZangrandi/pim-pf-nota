"""__main__.py — entrypoint único e idempotente da CLI.

Uso:
    python -m pim_report --periodo last     # mês mais recente publicado
    python -m pim_report --periodo 202504    # reprocessa/gera um mês específico

Saída: código 0 em sucesso (PDF + HTML gerados); 2 se o mês não foi publicado (Special Case);
1 em falha de domínio (mensagem acionável + log). Nunca um PDF silenciosamente errado.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import config
from .exceptions import PimReportError
from .pipeline import gerar_nota


def _configurar_logging(verboso: bool) -> None:
    nivel = logging.DEBUG if verboso else logging.INFO
    config.DIR_OUTPUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(config.DIR_OUTPUT / "pim_report.log", encoding="utf-8"),
        ],
    )


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="pim_report", description="Esteira da nota PIM-PF (IBGE).")
    p.add_argument(
        "--periodo",
        default="last",
        help="'last' (padrão) ou AAAAMM (ex.: 202504) para um mês específico.",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Logging em DEBUG.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    _configurar_logging(args.verbose)
    log = logging.getLogger("pim_report.cli")

    try:
        execucao = gerar_nota(periodo=args.periodo)
    except PimReportError as erro:
        log.error("FALHA: %s", erro)
        print(
            f"\n[ERRO] {erro}\nConsulte o log em {config.DIR_OUTPUT / 'pim_report.log'}.",
            file=sys.stderr,
        )
        return 1

    if not execucao.publicado:
        print(f"\n[AVISO] {execucao.mensagem}")
        return 2

    print(f"\n[OK] {execucao.mensagem}")
    print(f"  PDF : {execucao.pdf}")
    print(f"  HTML: {execucao.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
