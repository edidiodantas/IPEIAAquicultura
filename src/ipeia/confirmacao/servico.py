"""Trata os botões [Confirmar] / [Corrigir] / [Cancelar] e a justificativa de alertas.

Estados de uma pendência:
  aguardando --Confirmar (sem alerta)--> confirmada
  aguardando --Confirmar (com alerta)--> aguardando_justificativa --texto--> confirmada
  aguardando --Corrigir/Cancelar-------> cancelada
  qualquer estado aberto, após 24 h ---> expirada
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..banco.modelos import (Lote, Pendencia, StatusLancamento, StatusPendencia,
                             TipoLancamento)
from ..respostas import Resposta
from ..tempo import agora_utc, como_utc

ABERTOS = (StatusPendencia.aguardando, StatusPendencia.aguardando_justificativa)


def _encerrar(pendencia: Pendencia, status: StatusPendencia, status_lanc: StatusLancamento,
              agora: datetime) -> None:
    pendencia.status = status
    pendencia.resolvida_em = agora
    for l in pendencia.lancamentos:
        l.status = status_lanc


def _consolidar(sessao: Session, pendencia: Pendencia, telefone: str, agora: datetime,
                justificativa: str | None = None) -> None:
    """Torna os lançamentos definitivos e atualiza a quantidade de peixes do lote."""
    _encerrar(pendencia, StatusPendencia.confirmada, StatusLancamento.confirmado, agora)
    for l in pendencia.lancamentos:
        l.confirmado_por = telefone
        l.confirmado_em = agora
        l.justificativa = justificativa
        if not l.mortalidade or not l.lote_id:
            continue
        lote = sessao.get(Lote, l.lote_id)
        if l.tipo == TipoLancamento.estorno:
            lote.quantidade_atual += l.mortalidade  # devolve os mortos do lançamento estornado
        else:
            lote.quantidade_atual = max(0, lote.quantidade_atual - l.mortalidade)


def expirar_se_preciso(pendencia: Pendencia, agora: datetime) -> bool:
    if pendencia.status in ABERTOS and como_utc(pendencia.expira_em) <= agora:
        _encerrar(pendencia, StatusPendencia.expirada, StatusLancamento.expirado, agora)
        return True
    return False


def expirar_pendencias(sessao: Session, agora: datetime | None = None) -> int:
    """Rotina periódica (cron): expira pendências com mais de 24 h. Devolve quantas."""
    agora = agora or agora_utc()
    abertas = sessao.scalars(select(Pendencia).where(Pendencia.status.in_(ABERTOS)))
    return sum(expirar_se_preciso(p, agora) for p in abertas)


def tratar_botao(sessao: Session, fazenda_id: str, telefone: str, botao_id: str) -> Resposta:
    acao, _, pendencia_id = botao_id.partition(":")
    pendencia = sessao.get(Pendencia, pendencia_id)
    # Confere a fazenda e o telefone: um número não confirma lançamento de outro.
    if pendencia is None or pendencia.fazenda_id != fazenda_id or pendencia.telefone != telefone:
        return Resposta("Não encontrei esse lançamento.")

    agora = agora_utc()
    if expirar_se_preciso(pendencia, agora):
        return Resposta("⌛ Esse lançamento expirou (mais de 24 horas). Envie de novo, por favor.")
    if pendencia.status not in ABERTOS:
        return Resposta(f"Esse lançamento já foi {pendencia.status.value}.")

    if acao == "confirmar":
        if pendencia.tem_alerta and pendencia.status == StatusPendencia.aguardando:
            # RF05: alerta pode ser confirmado, mas com justificativa.
            pendencia.status = StatusPendencia.aguardando_justificativa
            return Resposta("Há valores fora do usual. Escreva em uma frase o motivo para registrar "
                            "mesmo assim (ou toque em Cancelar).")
        _consolidar(sessao, pendencia, telefone, agora)
        return Resposta("✅ Registrado.")
    if acao == "corrigir":
        _encerrar(pendencia, StatusPendencia.cancelada, StatusLancamento.cancelado, agora)
        return Resposta("Certo, descartei. Envie de novo o áudio ou o texto com os dados corretos.")
    if acao == "cancelar":
        _encerrar(pendencia, StatusPendencia.cancelada, StatusLancamento.cancelado, agora)
        return Resposta("❌ Cancelado. Nada foi registrado.")
    return Resposta("Não reconheci esse botão.")


def pendencia_aguardando_justificativa(sessao: Session, fazenda_id: str, telefone: str) -> Pendencia | None:
    return sessao.scalar(select(Pendencia).where(
        Pendencia.fazenda_id == fazenda_id, Pendencia.telefone == telefone,
        Pendencia.status == StatusPendencia.aguardando_justificativa,
    ).order_by(Pendencia.criada_em.desc()))


def registrar_justificativa(sessao: Session, pendencia: Pendencia, telefone: str, texto: str) -> Resposta:
    agora = agora_utc()
    if expirar_se_preciso(pendencia, agora):
        return Resposta("⌛ Esse lançamento expirou (mais de 24 horas). Envie de novo, por favor.")
    _consolidar(sessao, pendencia, telefone, agora, justificativa=texto.strip())
    return Resposta(f"✅ Registrado, com a justificativa: “{texto.strip()}”.")
