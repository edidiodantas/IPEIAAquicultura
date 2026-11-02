"""Roteamento de intenção (RF08).

O modelo só devolve rótulos de um conjunto fechado (decodificação guiada) e o
texto de cada trecho. Quem decide o fluxo é o código, no orquestrador. Uma
mensagem que mistura manejo e dúvida volta como dois segmentos.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, ValidationError

from ..inferencia.base import ModeloLinguagem
from ..inferencia.esquema import esquema_json


class Intencao(str, Enum):
    manejo = "manejo"
    consulta = "consulta"
    correcao = "correcao"
    outro = "outro"


class Segmento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intencao: Intencao
    texto: str


class SaidaRoteamento(BaseModel):
    model_config = ConfigDict(extra="forbid", title="roteamento")

    segmentos: list[Segmento]


PROMPT_ROTEAMENTO = """Classifique a mensagem de um piscicultor. Divida em trechos se ela tiver mais de um assunto.
Rótulos:
- manejo: relato do que foi feito ou visto hoje (ração dada, peixes mortos) para registrar.
- consulta: dúvida técnica ou biológica (doença, qualidade da água, nutrição, manejo).
- correcao: pedido para corrigir ou cancelar um lançamento já feito.
- outro: saudação, agradecimento ou qualquer outra coisa.
Copie o texto de cada trecho sem alterar. Responda só com JSON no esquema dado."""


def rotear(modelo: ModeloLinguagem, texto: str) -> list[Segmento]:
    bruto = modelo.gerar_json(PROMPT_ROTEAMENTO, texto, esquema_json(SaidaRoteamento))
    try:
        segmentos = SaidaRoteamento.model_validate(bruto).segmentos
    except ValidationError:
        return [Segmento(intencao=Intencao.outro, texto=texto)]
    return [s for s in segmentos if s.texto.strip()] or [Segmento(intencao=Intencao.outro, texto=texto)]
