from datetime import UTC, datetime

from ipeia.tempo import horario_do_manejo

FUSO = "America/Sao_Paulo"
# 02/11/2026 10:00 em Brasília = 13:00 UTC.
RECEBIDA = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)


def test_sem_hora_usa_recebimento():
    assert horario_do_manejo(RECEBIDA, FUSO) == RECEBIDA


def test_hora_dita():
    assert horario_do_manejo(RECEBIDA, FUSO, "07:00") == datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


def test_hora_no_futuro_vira_ontem():
    # Mensagem sem sinal: "tratei às 18h" chega às 10h do dia seguinte.
    assert horario_do_manejo(RECEBIDA, FUSO, "18:00") == datetime(2026, 11, 1, 21, 0, tzinfo=UTC)


def test_ontem():
    assert horario_do_manejo(RECEBIDA, FUSO, "07:00", 1) == datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
