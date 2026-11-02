import pytest

from ipeia.banco.sessao import transacao
from ipeia.cadastro import adicionar_tanque
from ipeia.banco.modelos import Fazenda
from ipeia.manejo.apelidos import cadastrar_apelido, interpretar_cadastro, normalizar, resolver_tanque


@pytest.mark.parametrize("entrada,esperado", [
    ("No Tanque da Entrada", "da entrada"),
    ("tanque do fundo", "do fundo"),
    ("T-3", "t3"),
    ("viveiro 2", "2"),
])
def test_normalizar(entrada, esperado):
    assert normalizar(entrada) == esperado


@pytest.mark.parametrize("dito,codigo", [
    ("tanque da entrada", "T1"),
    ("Tanque do fundo", "T3"),
    ("tanque 2", "T2"),
    ("T3", "T3"),
    ("tanque da entada", "T1"),  # erro de transcrição, busca aproximada
])
def test_resolve(fabrica, fazenda_id, dito, codigo):
    with transacao(fabrica) as s:
        r = resolver_tanque(s, fazenda_id, dito)
        assert r.status == "ok" and r.tanque.codigo == codigo


def test_desconhecido(fabrica, fazenda_id):
    with transacao(fabrica) as s:
        assert resolver_tanque(s, fazenda_id, "tanque da represa").status == "desconhecido"
        assert resolver_tanque(s, fazenda_id, "tanque 9").status == "desconhecido"


def test_ambiguo(fabrica, fazenda_id):
    with transacao(fabrica) as s:
        fazenda = s.get(Fazenda, fazenda_id)
        adicionar_tanque(s, fazenda, "T4", ["tanque do fundo novo"])
        adicionar_tanque(s, fazenda, "T5", ["tanque do fundo velho"])
        r = resolver_tanque(s, fazenda_id, "tanque do fundo v")
        assert r.status in {"ok", "ambiguo"}
        r = resolver_tanque(s, fazenda_id, "tanque do fundo")
        assert r.status == "ok" and r.tanque.codigo == "T3"  # exato vence o aproximado


def test_cadastro_de_apelido(fabrica, fazenda_id):
    assert interpretar_cadastro("apelido tanque grande = T2") == ("tanque grande", "T2")
    assert interpretar_cadastro("30 kg no tanque 2") is None
    with transacao(fabrica) as s:
        assert cadastrar_apelido(s, fazenda_id, "tanque grande", "t2").codigo == "T2"
        s.flush()
        assert resolver_tanque(s, fazenda_id, "tanque grande").tanque.codigo == "T2"
        assert cadastrar_apelido(s, fazenda_id, "x", "T99") is None
