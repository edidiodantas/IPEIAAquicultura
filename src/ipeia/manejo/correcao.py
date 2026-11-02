"""Correção e estorno de lançamentos confirmados (RF10).

O original nunca é apagado nem alterado. A correção gera, numa só pendência:
  1. um lançamento de estorno ligado ao original (estorna_id), e
  2. no caso de "corrigir", um novo lançamento com os valores certos.
Os dois só valem depois do [Confirmar], como qualquer lançamento (RF02).
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from ..banco.modelos import Lancamento, TipoLancamento
from ..contexto import Contexto
from ..respostas import Resposta, botoes_confirmacao
from ..tempo import como_utc
from .apelidos import resolver_tanque
from .extracao import ErroExtracao, extrair_correcao
from .registros import lote_ativo, racao_no_dia_kg, ultimo_confirmado
from .resumo import texto_bloqueio, texto_resumo
from .servico import ItemPreparado, contexto_lote, criar_pendencia, mensagem_tanque_nao_resolvido
from .unidades import para_kg
from .validacao import Nivel, ResultadoValidacao, validar


def processar_correcao(ctx: Contexto, texto: str) -> Resposta:
    try:
        pedido = extrair_correcao(ctx.modelo, texto)
    except ErroExtracao:
        return Resposta("Não entendi a correção. Diga o tanque, o dia e o valor certo, por exemplo: "
                        "“o de ontem no tanque 2 foi 20 kg, não 30”.")

    resolvido = resolver_tanque(ctx.sessao, ctx.fazenda.id, pedido.tanque)
    if resolvido.status != "ok":
        return Resposta(mensagem_tanque_nao_resolvido(ctx, pedido.tanque, resolvido))
    tanque = resolvido.tanque

    # "ontem" -> procura só no dia de ontem; sem dia, pega o último lançamento.
    dia = None
    if pedido.dias_atras is not None:
        hoje = como_utc(ctx.mensagem.recebida_em).astimezone(ZoneInfo(ctx.cfg.fuso_horario)).date()
        dia = hoje - timedelta(days=pedido.dias_atras)
    original = ultimo_confirmado(ctx.sessao, ctx.fazenda.id, tanque.id, dia, ctx.cfg.fuso_horario)
    if original is None:
        return Resposta(f"Não achei lançamento confirmado no {tanque.codigo}"
                        + (f" em {dia:%d/%m}" if dia else "") + " para corrigir.")

    # Estorno: repete os valores do original, com tipo "estorno".
    estorno = ItemPreparado(
        tanque=tanque, lote_id=original.lote_id, racao_kg=original.racao_kg,
        tipo_racao=original.tipo_racao, mortalidade=original.mortalidade,
        manejo_em=original.manejo_em, extraido=pedido.model_dump(),
        validacao=ResultadoValidacao(nivel=Nivel.ok, mensagens=[]),
    )
    preparados = [estorno]

    if pedido.acao == "corrigir":
        # O que não foi dito na correção herda do original.
        racao = para_kg(pedido.quantidade_racao, pedido.unidade_racao, ctx.peso_saco_kg)
        racao = original.racao_kg if racao is None else racao
        mortalidade = original.mortalidade if pedido.mortalidade is None else pedido.mortalidade
        lote = lote_ativo(ctx.sessao, tanque.id)
        contexto = contexto_lote(lote)
        if contexto is not None and original.mortalidade:
            # O estorno devolve ao lote os mortos do original antes de validar o novo valor.
            contexto.quantidade_atual += original.mortalidade
        resultado = validar(
            {"tanque_codigo": tanque.codigo, "racao_kg": racao, "tipo_racao": original.tipo_racao,
             "mortalidade": mortalidade},
            ctx.limites, contexto,
            racao_no_dia_kg(ctx.sessao, ctx.fazenda.id, tanque.id, original.manejo_em,
                            ctx.cfg.fuso_horario, ignorar_id=original.id),
        )
        if resultado.nivel == Nivel.bloqueio:
            return Resposta(texto_bloqueio(resultado.mensagens))
        preparados.append(ItemPreparado(tanque, lote.id if lote else original.lote_id, racao,
                                        original.tipo_racao, mortalidade, original.manejo_em,
                                        pedido.model_dump(), resultado))

    pendencia = criar_pendencia(ctx, preparados)
    # Marca o primeiro lançamento como estorno do original.
    primeiro: Lancamento = pendencia.lancamentos[0]
    primeiro.tipo = TipoLancamento.estorno
    primeiro.estorna_id = original.id
    return Resposta(texto_resumo(ctx, texto, pendencia), botoes_confirmacao(pendencia.id))
