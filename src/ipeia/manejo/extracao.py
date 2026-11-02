"""Extração estruturada de entidades operacionais (RF03)."""

from pydantic import ValidationError

from ..inferencia.base import ModeloLinguagem
from ..inferencia.esquema import esquema_json
from .esquemas import ItemManejo, SaidaCorrecao, SaidaExtracao

PROMPT_EXTRACAO = """Você extrai dados de manejo de piscicultura de mensagens de produtores brasileiros.
Responda somente com JSON no esquema dado. Regras:
- Crie um item para cada tanque citado. Mantenha o nome do tanque como foi dito ("tanque da entrada", "tanque 3").
- Quantidade de ração: número e unidade (kg, g ou saco). "Meio saco" = 0.5 saco. "Um saco e meio" = 1.5 saco.
- Mortalidade: número de peixes mortos. "Nenhum morto" = 0. Se não falou, null.
- Hora do manejo só se foi dita ("às 7h" = "07:00"). "Ontem" = dias_atras 1.
- Nunca invente valores: o que não foi dito fica null."""

PROMPT_CORRECAO = """Você interpreta pedidos de correção de lançamentos de manejo de piscicultura.
Responda somente com JSON no esquema dado.
- acao "estornar" se o produtor quer cancelar o lançamento; "corrigir" se quer trocar valores.
- Os valores são os NOVOS, corretos ("foi 20 kg, não 30" = 20 kg).
- dias_atras: 1 para "ontem", 0 para "hoje", null se não disse."""


class ErroExtracao(ValueError):
    pass


def extrair_manejo(modelo: ModeloLinguagem, texto: str) -> list[ItemManejo]:
    bruto = modelo.gerar_json(PROMPT_EXTRACAO, texto, esquema_json(SaidaExtracao))
    try:
        return SaidaExtracao.model_validate(bruto).itens
    except ValidationError as exc:
        raise ErroExtracao(str(exc)) from exc


def extrair_correcao(modelo: ModeloLinguagem, texto: str) -> SaidaCorrecao:
    bruto = modelo.gerar_json(PROMPT_CORRECAO, texto, esquema_json(SaidaCorrecao))
    try:
        return SaidaCorrecao.model_validate(bruto)
    except ValidationError as exc:
        raise ErroExtracao(str(exc)) from exc
