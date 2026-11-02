"""Horários do registro (RNF06).

Cada lançamento guarda três horários: o do manejo (dito no áudio ou, na falta
dele, o do WhatsApp), o de recebimento pelo WhatsApp e o de processamento.
Tudo é gravado em UTC; o fuso só é usado para interpretar "às 7h" e "ontem".
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo


def agora_utc() -> datetime:
    return datetime.now(UTC)


def de_timestamp_whatsapp(ts: str | int) -> datetime:
    """O WhatsApp envia o horário de recebimento em segundos Unix."""
    return datetime.fromtimestamp(int(ts), UTC)


def horario_do_manejo(
    recebido_em: datetime,
    fuso: str,
    hora_dita: str | None = None,
    dias_atras: int | None = None,
) -> datetime:
    """Combina o que o produtor disse ("ontem às 7h") com a data do WhatsApp.

    Sem hora dita, usa o horário de recebimento. Se a hora dita cair no futuro
    em relação ao recebimento (ex.: "às 23h" recebido às 6h), assume o dia anterior.
    """
    tz = ZoneInfo(fuso)
    local = recebido_em.astimezone(tz)
    if hora_dita is None and not dias_atras:
        return recebido_em.astimezone(UTC)

    dia = local.date() - timedelta(days=dias_atras or 0)
    if hora_dita:
        h, _, m = hora_dita.partition(":")
        hora = time(int(h), int(m or 0))
    else:
        hora = local.time().replace(microsecond=0)
    resultado = datetime.combine(dia, hora, tz)
    if not dias_atras and resultado > local:
        resultado -= timedelta(days=1)
    return resultado.astimezone(UTC)


def como_utc(dt: datetime) -> datetime:
    """SQLite devolve datas sem fuso; tratamos todas como UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
