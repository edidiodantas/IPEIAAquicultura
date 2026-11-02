"""Conversão de unidades de ração para kg (RF03)."""


def para_kg(quantidade: float | None, unidade: str | None, peso_saco_kg: float) -> float | None:
    if quantidade is None:
        return None
    if unidade == "saco":
        return round(quantidade * peso_saco_kg, 3)
    if unidade == "g":
        return round(quantidade / 1000, 3)
    return round(quantidade, 3)  # kg ou unidade omitida
