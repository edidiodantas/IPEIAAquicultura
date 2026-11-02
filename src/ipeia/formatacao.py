"""Formatação de números no padrão brasileiro para as mensagens ao produtor."""


def num(valor: float, casas: int | None = None) -> str:
    """12.5 -> '12,5'; num(4.333, 1) -> '4,3'."""
    texto = f"{valor:.{casas}f}" if casas is not None else f"{valor:g}"
    return texto.replace(".", ",")
