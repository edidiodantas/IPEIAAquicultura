"""Isolamento por fazenda no PostgreSQL real (RNF07). Pulado se não houver banco.

Para rodar, aponte duas URLs para um banco vazio:
  IPEIA_TEST_PG_DONO  papel dono das tabelas (cria tabelas e aplica sql/rls_postgres.sql)
  IPEIA_TEST_PG_APP   papel da aplicação, sem BYPASSRLS e sem ser dono
"""

import os

import pytest
from sqlalchemy import func, select, text

from ipeia.banco.modelos import Base, Lancamento, Tanque
from ipeia.banco.sessao import criar_engine, criar_tabelas, definir_fazenda, fabrica_de_sessoes, transacao
from ipeia.cadastro import criar_fazenda_demo
from ipeia.config import RAIZ_PROJETO

DONO, APP = os.getenv("IPEIA_TEST_PG_DONO"), os.getenv("IPEIA_TEST_PG_APP")
pytestmark = pytest.mark.skipif(not (DONO and APP), reason="PostgreSQL de teste não configurado")


def test_fazenda_nao_ve_dados_de_outra():
    dono = criar_engine(DONO)
    Base.metadata.drop_all(dono)
    criar_tabelas(dono)
    with dono.begin() as c:
        # Conexão do driver, sem parâmetros, para o psycopg não interpretar os % do format().
        c.connection.driver_connection.execute((RAIZ_PROJETO / "sql" / "rls_postgres.sql").read_text())
        nome_app = APP.split("://", 1)[1].split("@", 1)[0].split(":")[0]
        c.execute(text(f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO "{nome_app}"'))
    with transacao(fabrica_de_sessoes(dono)) as s:
        a = criar_fazenda_demo(s, telefone="5500000000001").id
        b = criar_fazenda_demo(s, telefone="5500000000002").id

    app = fabrica_de_sessoes(criar_engine(APP))
    with transacao(app) as s:
        assert s.scalar(select(func.count()).select_from(Tanque)) == 0  # sem fazenda, nada
    with transacao(app) as s:
        definir_fazenda(s, a)
        assert set(s.scalars(select(Tanque.fazenda_id))) == {a}
    with transacao(app) as s, pytest.raises(Exception):
        definir_fazenda(s, a)
        s.add(Lancamento(fazenda_id=b, tanque_id="x", manejo_em=func.now(), recebido_em=func.now()))
        s.flush()  # WITH CHECK impede gravar na fazenda B estando na A
