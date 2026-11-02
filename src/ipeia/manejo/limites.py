"""Tabela de limites zootécnicos carregada de config/limites.toml (RF05)."""

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class LimitesFase(BaseModel):
    racao_pct_biomassa_alerta: float = Field(gt=0)
    racao_pct_biomassa_bloqueio: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordem(self):
        if self.racao_pct_biomassa_bloqueio < self.racao_pct_biomassa_alerta:
            raise ValueError("o limite de bloqueio deve ser maior que o de alerta")
        return self


class LimitesEspecie(BaseModel):
    nome: str
    mortalidade_pct_diaria_alerta: float = Field(gt=0)
    mortalidade_pct_diaria_bloqueio: float = Field(gt=0)
    fases: dict[str, LimitesFase]


class LimitesGerais(BaseModel):
    peso_saco_kg_padrao: float = 25.0
    expiracao_pendencia_horas: int = 24
    racao_maxima_sem_lote_kg: float = 50.0


class TabelaLimites(BaseModel):
    versao: str
    responsavel: str
    geral: LimitesGerais = LimitesGerais()
    especies: dict[str, LimitesEspecie]

    def da_fase(self, especie: str, fase: str) -> tuple[LimitesEspecie, LimitesFase] | None:
        e = self.especies.get(especie)
        if e is None or fase not in e.fases:
            return None
        return e, e.fases[fase]


def carregar_limites(caminho: Path) -> TabelaLimites:
    with open(caminho, "rb") as f:
        return TabelaLimites.model_validate(tomllib.load(f))


@lru_cache
def limites_em_cache(caminho: Path) -> TabelaLimites:
    return carregar_limites(caminho)
