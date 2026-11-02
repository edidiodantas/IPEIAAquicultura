"""Esquemas da saída do modelo para o manejo (RF03) e a correção (RF10).

Estes modelos são enviados ao Amadeus-Verbo como esquema JSON (decodificação
guiada) e depois usados para validar a resposta. Eles descrevem só o que foi
dito; a validação zootécnica fica em `validacao.py`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Unidade = Literal["kg", "g", "saco"]


class ItemManejo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tanque: str = Field(description="Tanque como o produtor falou: código ou apelido.")
    quantidade_racao: float | None = Field(description="Quantidade de ração dita. 'Meio saco' = 0.5.")
    unidade_racao: Unidade | None = Field(description="Unidade da quantidade de ração.")
    tipo_racao: str | None = Field(description="Fase ou tipo da ração (ex.: '4 mm', '32%', 'engorda').")
    mortalidade: int | None = Field(description="Número de peixes mortos vistos.")
    hora_manejo: str | None = Field(description="Hora dita, no formato HH:MM, ou null.")
    dias_atras: int | None = Field(description="1 se disse 'ontem', 2 se 'anteontem', senão null.")


class SaidaExtracao(BaseModel):
    model_config = ConfigDict(extra="forbid", title="extracao_manejo")

    itens: list[ItemManejo] = Field(description="Um item por tanque citado.")


class SaidaCorrecao(BaseModel):
    model_config = ConfigDict(extra="forbid", title="correcao")

    acao: Literal["corrigir", "estornar"]
    tanque: str
    dias_atras: int | None
    quantidade_racao: float | None
    unidade_racao: Unidade | None
    mortalidade: int | None
