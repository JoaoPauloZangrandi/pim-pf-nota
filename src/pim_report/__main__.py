"""__main__.py — entrypoint único e idempotente da CLI.

Uso: python -m pim_report --periodo last   (mês mais recente publicado)
     python -m pim_report --periodo AAAAMM  (reprocessa um mês a partir do cache)

A ser implementado na Etapa 7.
"""


def main() -> int:
    """Ponto de entrada da CLI. A ser implementado na Etapa 7."""
    raise NotImplementedError("CLI a ser implementada na Etapa 7.")


if __name__ == "__main__":
    raise SystemExit(main())
