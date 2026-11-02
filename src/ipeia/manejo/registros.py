"""Consultas aos lançamentos já gravados, usadas pela validação e pela correção."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..banco.modelos import Lancamento, Lote, StatusLancamento, TipoLancamento
from ..tempo import como_utc


def lote_ativo(sessao: Session, tanque_id: str) -> Lote | None:
    # Se houver mais de um lote ativo por engano de cadastro, usa o mais recente.
    return sessao.scalar(select(Lote).where(Lote.tanque_id == tanque_id, Lote.ativo.is_(True))
                         .order_by(Lote.povoado_em.desc()))


def _ids_estornados(sessao: Session, fazenda_id: str) -> set[str]:
    """IDs de lançamentos que já têm um estorno confirmado."""
    return set(sessao.scalars(select(Lancamento.estorna_id).where(
        Lancamento.fazenda_id == fazenda_id,
        Lancamento.tipo == TipoLancamento.estorno,
        Lancamento.status == StatusLancamento.confirmado)))


def _limites_do_dia(momento: datetime, fuso: str) -> tuple[datetime, datetime]:
    """Início e fim (em UTC) do dia local que contém `momento`."""
    tz = ZoneInfo(fuso)
    dia = momento.astimezone(tz).date()
    inicio = datetime.combine(dia, time.min, tz)
    return inicio.astimezone(UTC), (inicio + timedelta(days=1)).astimezone(UTC)


def confirmados_no_dia(sessao: Session, fazenda_id: str, tanque_id: str, momento: datetime,
                       fuso: str) -> list[Lancamento]:
    """Manejos confirmados no mesmo tanque e no mesmo dia local, sem os estornados."""
    inicio, fim = _limites_do_dia(momento, fuso)
    estornados = _ids_estornados(sessao, fazenda_id)
    candidatos = sessao.scalars(select(Lancamento).where(
        Lancamento.fazenda_id == fazenda_id,
        Lancamento.tanque_id == tanque_id,
        Lancamento.tipo == TipoLancamento.manejo,
        Lancamento.status == StatusLancamento.confirmado))
    # Filtro de data em Python porque o SQLite não guarda o fuso.
    return [l for l in candidatos
            if inicio <= como_utc(l.manejo_em) < fim and l.id not in estornados]


def racao_no_dia_kg(sessao: Session, fazenda_id: str, tanque_id: str, momento: datetime, fuso: str,
                    ignorar_id: str | None = None) -> float:
    """Soma a ração já confirmada no dia (RF05 compara o total do dia com a biomassa)."""
    return sum(l.racao_kg or 0.0 for l in confirmados_no_dia(sessao, fazenda_id, tanque_id, momento, fuso)
               if l.id != ignorar_id)


def ultimo_confirmado(sessao: Session, fazenda_id: str, tanque_id: str, dia_local=None,
                      fuso: str = "America/Sao_Paulo") -> Lancamento | None:
    """Último manejo confirmado e ainda não estornado de um tanque (RF10)."""
    estornados = _ids_estornados(sessao, fazenda_id)
    candidatos = sessao.scalars(select(Lancamento).where(
        Lancamento.fazenda_id == fazenda_id,
        Lancamento.tanque_id == tanque_id,
        Lancamento.tipo == TipoLancamento.manejo,
        Lancamento.status == StatusLancamento.confirmado,
    ).order_by(Lancamento.manejo_em.desc(), Lancamento.processado_em.desc()))
    tz = ZoneInfo(fuso)
    for l in candidatos:
        if l.id in estornados:
            continue
        if dia_local is not None and como_utc(l.manejo_em).astimezone(tz).date() != dia_local:
            continue
        return l
    return None
