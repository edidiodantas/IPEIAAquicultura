"""Fluxo de manejo: texto -> itens extraídos -> tanques -> validação -> pendência.

Ordem definida na v2: primeiro valida (RF05), depois pede confirmação (RF02).
Se qualquer item for barrado, nada da mensagem é gravado como pendente, para
o produtor não confirmar metade de um relato.
"""

from dataclasses import dataclass
from datetime import timedelta

from ..banco.modelos import Lancamento, Pendencia, Tanque
from ..contexto import Contexto
from ..respostas import Resposta, botoes_confirmacao
from ..tempo import agora_utc, como_utc, horario_do_manejo
from .apelidos import resolver_tanque
from .esquemas import ItemManejo
from .extracao import ErroExtracao, extrair_manejo
from .registros import lote_ativo, racao_no_dia_kg
from .resumo import texto_bloqueio, texto_resumo
from .unidades import para_kg
from .validacao import ContextoLote, Nivel, ResultadoValidacao, validar


@dataclass
class ItemPreparado:
    """Um item pronto para virar lançamento pendente."""

    tanque: Tanque
    lote_id: str | None
    racao_kg: float | None
    tipo_racao: str | None
    mortalidade: int | None
    manejo_em: object  # datetime em UTC
    extraido: dict
    validacao: ResultadoValidacao


def _somar(valores):
    """Soma ignorando None; devolve None se nada foi dito."""
    ditos = [v for v in valores if v is not None]
    return sum(ditos) if ditos else None


def contexto_lote(lote) -> ContextoLote | None:
    if lote is None:
        return None
    return ContextoLote(especie=lote.especie, fase=lote.fase, quantidade_atual=lote.quantidade_atual,
                        peso_medio_g=lote.peso_medio_g)


def mensagem_tanque_nao_resolvido(ctx: Contexto, dito: str, resultado) -> str:
    """Texto do RF04 para apelido ambíguo ou desconhecido."""
    if resultado.status == "ambiguo":
        opcoes = " ou ".join(t.codigo for t in resultado.candidatos)
        return f"“{dito}”: fiquei em dúvida entre {opcoes}. Diga o código do tanque."
    codigos = ", ".join(sorted(t.codigo for t in ctx.fazenda.tanques)) or "nenhum"
    return (f"“{dito}”: não conheço esse tanque. Tanques cadastrados: {codigos}. "
            f"Para criar o apelido, envie: apelido {dito} = <código>")


def processar_manejo(ctx: Contexto, texto: str) -> Resposta:
    try:
        itens = extrair_manejo(ctx.modelo, texto)
    except ErroExtracao:
        return Resposta("Não consegui entender o lançamento. Pode repetir dizendo o tanque, "
                        "a quantidade de ração e se houve peixes mortos?")
    if not itens:
        return Resposta("Não identifiquei o tanque. Diga, por exemplo: “30 kg no tanque 3, 2 mortos”.")

    problemas: list[str] = []
    preparados: list[ItemPreparado] = []
    recebida_em = como_utc(ctx.mensagem.recebida_em)

    # RF04: apelido -> tanque cadastrado. Itens do mesmo tanque são somados
    # ("meio saco no tanque do meio ... morreram 3 no tanque do meio").
    por_tanque: dict[str, tuple[Tanque, list[ItemManejo]]] = {}
    for item in itens:
        resolvido = resolver_tanque(ctx.sessao, ctx.fazenda.id, item.tanque)
        if resolvido.status != "ok":
            problemas.append(mensagem_tanque_nao_resolvido(ctx, item.tanque, resolvido))
            continue
        por_tanque.setdefault(resolvido.tanque.id, (resolvido.tanque, []))[1].append(item)

    for tanque, grupo in por_tanque.values():
        lote = lote_ativo(ctx.sessao, tanque.id)

        # RF03: unidades -> kg; RNF06: horário do manejo dito ou o do WhatsApp.
        racao_kg = _somar(para_kg(i.quantidade_racao, i.unidade_racao, ctx.peso_saco_kg) for i in grupo)
        mortalidade = _somar(i.mortalidade for i in grupo)
        tipo_racao = next((i.tipo_racao for i in grupo if i.tipo_racao), None)
        hora = next((i.hora_manejo for i in grupo if i.hora_manejo), None)
        dias = next((i.dias_atras for i in grupo if i.dias_atras), None)
        manejo_em = horario_do_manejo(recebida_em, ctx.cfg.fuso_horario, hora, dias)

        # RF05: validação por código, somando o que já foi dado no dia.
        resultado = validar(
            {"tanque_codigo": tanque.codigo, "racao_kg": racao_kg, "tipo_racao": tipo_racao,
             "mortalidade": mortalidade},
            ctx.limites, contexto_lote(lote),
            racao_no_dia_kg(ctx.sessao, ctx.fazenda.id, tanque.id, manejo_em, ctx.cfg.fuso_horario),
        )
        if resultado.nivel == Nivel.bloqueio:
            problemas.extend(resultado.mensagens)
            continue
        extraido = {"itens": [i.model_dump() for i in grupo]}  # o que o modelo devolveu (RNF09)
        preparados.append(ItemPreparado(tanque, lote.id if lote else None, racao_kg, tipo_racao,
                                        mortalidade, manejo_em, extraido, resultado))

    if problemas:
        return Resposta(texto_bloqueio(problemas))

    pendencia = criar_pendencia(ctx, preparados)
    return Resposta(texto_resumo(ctx, texto, pendencia), botoes_confirmacao(pendencia.id))


def criar_pendencia(ctx: Contexto, preparados: list[ItemPreparado]) -> Pendencia:
    """Grava os lançamentos como pendentes; só o [Confirmar] os torna definitivos (RF02)."""
    agora = agora_utc()
    pendencia = Pendencia(
        fazenda_id=ctx.fazenda.id, telefone=ctx.usuario.telefone, criada_em=agora,
        expira_em=agora + timedelta(hours=ctx.limites.geral.expiracao_pendencia_horas),
        tem_alerta=any(p.validacao.nivel == Nivel.alerta for p in preparados),
    )
    ctx.sessao.add(pendencia)
    for p in preparados:
        ctx.sessao.add(Lancamento(
            fazenda_id=ctx.fazenda.id, pendencia=pendencia, mensagem_id=ctx.mensagem.id,
            tanque=p.tanque, lote_id=p.lote_id, racao_kg=p.racao_kg, tipo_racao=p.tipo_racao,
            mortalidade=p.mortalidade, manejo_em=p.manejo_em, recebido_em=ctx.mensagem.recebida_em,
            processado_em=agora, json_extraido=p.extraido, validacao=p.validacao.para_json(),
        ))
    ctx.sessao.flush()  # gera os IDs usados nos botões
    return pendencia
