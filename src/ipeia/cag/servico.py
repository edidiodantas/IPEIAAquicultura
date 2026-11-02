"""Fluxo de consulta técnica: responde e grava a consulta para auditoria (RNF10)."""

from ..banco.modelos import ConsultaTecnica
from ..contexto import Contexto
from ..respostas import Resposta
from .consulta import responder


def processar_consulta(ctx: Contexto, pergunta: str) -> Resposta:
    resultado = responder(ctx.modelo, ctx.acervo, pergunta)
    ctx.sessao.add(ConsultaTecnica(
        fazenda_id=ctx.fazenda.id, mensagem_id=ctx.mensagem.id, pergunta=pergunta,
        bloco=resultado.bloco, versao_acervo=resultado.versao_acervo,
        resposta_enviada=resultado.texto, citacao=resultado.citacao,
        citacao_verificada=resultado.verificada,
    ))
    return Resposta(resultado.texto)
