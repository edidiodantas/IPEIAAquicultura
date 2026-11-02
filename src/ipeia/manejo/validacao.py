"""Validação de limites zootécnicos por código (RF05), primeira camada de proteção.

Os números vêm de config/limites.toml e do cadastro do lote, nunca do modelo.
Um bloqueio vira `ValidationError` do Pydantic; alertas ficam na lista `alertas`.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, model_validator

from ..formatacao import num
from .limites import TabelaLimites


class Nivel(str, Enum):
    ok = "ok"
    alerta = "alerta"
    bloqueio = "bloqueio"


class ContextoLote(BaseModel):
    especie: str
    fase: str
    quantidade_atual: int
    peso_medio_g: float

    @property
    def biomassa_kg(self) -> float:
        return self.quantidade_atual * self.peso_medio_g / 1000


class ManejoValidado(BaseModel):
    """Um item de manejo já com tanque resolvido e ração em kg.

    Contexto obrigatório em `model_validate(..., context=...)`:
      limites: TabelaLimites
      lote: ContextoLote | None
      racao_no_dia_kg: float (ração já confirmada hoje neste tanque)
    """

    tanque_codigo: str
    racao_kg: float | None = None
    tipo_racao: str | None = None
    mortalidade: int | None = None
    alertas: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _limites_zootecnicos(self, info: ValidationInfo) -> "ManejoValidado":
        ctx = info.context or {}
        limites: TabelaLimites = ctx["limites"]
        lote: ContextoLote | None = ctx.get("lote")
        racao_no_dia = float(ctx.get("racao_no_dia_kg", 0.0))
        t = self.tanque_codigo

        if self.racao_kg is None and self.mortalidade is None:
            raise ValueError(f"{t}: não entendi a quantidade de ração nem a mortalidade.")
        if self.racao_kg is not None and self.racao_kg < 0:
            raise ValueError(f"{t}: a quantidade de ração não pode ser negativa.")
        if self.mortalidade is not None and self.mortalidade < 0:
            raise ValueError(f"{t}: a mortalidade não pode ser negativa.")

        if lote is None:
            if self.mortalidade:
                raise ValueError(f"{t}: há mortalidade relatada, mas o tanque não tem lote ativo cadastrado.")
            if self.racao_kg and self.racao_kg > limites.geral.racao_maxima_sem_lote_kg:
                raise ValueError(f"{t}: {num(self.racao_kg)} kg de ração num tanque sem lote ativo cadastrado.")
            if self.racao_kg:
                self.alertas.append(f"{t}: o tanque não tem lote ativo cadastrado.")
            return self

        if self.mortalidade:
            if self.mortalidade > lote.quantidade_atual:
                raise ValueError(f"{t}: {self.mortalidade} mortos, mas o lote tem só "
                                 f"{lote.quantidade_atual} peixes.")
        faixa = limites.da_fase(lote.especie, lote.fase)
        if faixa is None:
            self.alertas.append(f"{t}: não há limites cadastrados para {lote.especie}/{lote.fase}; "
                                "a validação foi parcial.")
            return self
        especie, fase = faixa

        if self.mortalidade:
            pct = 100 * self.mortalidade / lote.quantidade_atual
            if pct > especie.mortalidade_pct_diaria_bloqueio:
                raise ValueError(f"{t}: mortalidade de {num(pct, 1)}% do lote num só dia está acima do limite "
                                 f"de {num(especie.mortalidade_pct_diaria_bloqueio)}%. Confira o número.")
            if pct > especie.mortalidade_pct_diaria_alerta:
                self.alertas.append(f"{t}: mortalidade de {num(pct, 1)}% do lote (o usual é até "
                                    f"{num(especie.mortalidade_pct_diaria_alerta)}% ao dia).")

        if self.racao_kg and lote.biomassa_kg > 0:
            total = self.racao_kg + racao_no_dia
            pct = 100 * total / lote.biomassa_kg
            if pct > fase.racao_pct_biomassa_bloqueio:
                raise ValueError(f"{t}: {num(total)} kg de ração no dia são {num(pct, 1)}% da biomassa "
                                 f"({num(lote.biomassa_kg)} kg), acima do máximo de "
                                 f"{num(fase.racao_pct_biomassa_bloqueio)}%.")
            if pct > fase.racao_pct_biomassa_alerta:
                self.alertas.append(f"{t}: {num(total)} kg de ração no dia são {num(pct, 1)}% da biomassa "
                                    f"(o usual é até {num(fase.racao_pct_biomassa_alerta)}%).")
        return self


class ResultadoValidacao(BaseModel):
    nivel: Nivel
    mensagens: list[str]

    def para_json(self) -> dict[str, Any]:
        return {"nivel": self.nivel.value, "mensagens": self.mensagens}


def validar(dados: dict[str, Any], limites: TabelaLimites, lote: ContextoLote | None,
            racao_no_dia_kg: float = 0.0) -> ResultadoValidacao:
    try:
        item = ManejoValidado.model_validate(
            dados, context={"limites": limites, "lote": lote, "racao_no_dia_kg": racao_no_dia_kg})
    except ValidationError as exc:
        mensagens = [str(e["ctx"]["error"]) if "ctx" in e and "error" in e["ctx"] else e["msg"]
                     for e in exc.errors()]
        return ResultadoValidacao(nivel=Nivel.bloqueio, mensagens=mensagens)
    nivel = Nivel.alerta if item.alertas else Nivel.ok
    return ResultadoValidacao(nivel=nivel, mensagens=list(item.alertas))
