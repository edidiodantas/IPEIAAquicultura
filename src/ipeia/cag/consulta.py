"""Resposta a dúvidas técnicas com barreira de citação (RF06, RF07, RNF02, RNF03).

1. O modelo escolhe um bloco do acervo (saída restrita aos nomes dos blocos).
2. O modelo responde com temperatura 0, usando só o bloco, e devolve o trecho literal.
3. O código confere se o trecho existe no bloco. Se não existir, a resposta é
   descartada e vai a frase padrão.
4. O código anexa a fonte e o aviso legal.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ..inferencia.base import ModeloLinguagem
from ..inferencia.esquema import esquema_json
from .acervo import Acervo, Bloco
from .textos import AVISO_LEGAL, FRASE_NAO_ENCONTRADO


class SaidaResposta(BaseModel):
    model_config = ConfigDict(extra="forbid", title="resposta_tecnica")

    encontrado: bool
    resposta: str
    citacao_literal: str


PROMPT_ESCOLHA = """Escolha o bloco de manuais técnicos que responde à pergunta do piscicultor.
Se nenhum servir, escolha "nenhum". Blocos disponíveis:
{lista}"""

PROMPT_RESPOSTA = """Você é um assistente técnico de piscicultura. Responda SOMENTE com base nos manuais abaixo.
Regras obrigatórias:
- Se a resposta não estiver nos manuais, devolva encontrado=false, resposta e citacao_literal vazias. Não deduza.
- citacao_literal deve ser uma cópia exata, palavra por palavra, de um trecho dos manuais que sustenta a resposta.
- Responda em português simples, em até 4 frases, sem inventar doses, prazos ou produtos.
- Não escreva avisos legais; o sistema os adiciona.

<acervo>
{acervo}
</acervo>"""


@dataclass(frozen=True)
class RespostaTecnica:
    texto: str
    bloco: str | None
    versao_acervo: str | None
    citacao: str | None
    verificada: bool


def _esquema_escolha(acervo: Acervo) -> dict[str, Any]:
    return {
        "title": "escolha_bloco",
        "type": "object",
        "properties": {"bloco": {"type": "string", "enum": [*acervo.blocos.keys(), "nenhum"]}},
        "required": ["bloco"],
        "additionalProperties": False,
    }


def escolher_bloco(modelo: ModeloLinguagem, acervo: Acervo, pergunta: str) -> Bloco | None:
    if not acervo.blocos:
        return None
    if len(acervo.blocos) == 1:
        return next(iter(acervo.blocos.values()))
    lista = "\n".join(f"- {b.nome}: {b.descricao}" for b in acervo.blocos.values())
    bruto = modelo.gerar_json(PROMPT_ESCOLHA.format(lista=lista), pergunta, _esquema_escolha(acervo))
    return acervo.blocos.get(bruto.get("bloco", ""))


def prompt_do_bloco(bloco: Bloco) -> str:
    """Prefixo fixo por bloco: mesmo texto sempre, para acertar o KV-Cache (RNF05)."""
    return PROMPT_RESPOSTA.format(acervo=bloco.texto_para_prompt())


def nao_encontrado(bloco: Bloco | None = None, citacao: str | None = None) -> RespostaTecnica:
    return RespostaTecnica(FRASE_NAO_ENCONTRADO, bloco.nome if bloco else None,
                           bloco.versao_completa if bloco else None, citacao, False)


def responder(modelo: ModeloLinguagem, acervo: Acervo, pergunta: str) -> RespostaTecnica:
    bloco = escolher_bloco(modelo, acervo, pergunta)
    if bloco is None:
        return nao_encontrado()

    bruto = modelo.gerar_json(prompt_do_bloco(bloco), pergunta, esquema_json(SaidaResposta))
    try:
        saida = SaidaResposta.model_validate(bruto)
    except ValidationError:
        return nao_encontrado(bloco)
    if not saida.encontrado or not saida.resposta.strip():
        return nao_encontrado(bloco)

    local = bloco.localizar(saida.citacao_literal)
    if local is None:
        return nao_encontrado(bloco, saida.citacao_literal)

    pagina = f", p. {local.pagina}" if local.pagina != "?" else ""
    texto = (f"{saida.resposta.strip()}\n\n"
             f"📖 Fonte: {local.manual.titulo}{pagina}: “{saida.citacao_literal.strip()}”\n\n"
             f"{AVISO_LEGAL}")
    return RespostaTecnica(texto, bloco.nome, bloco.versao_completa, saida.citacao_literal, True)
