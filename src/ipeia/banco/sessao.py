"""Conexão com o banco e definição da fazenda corrente para o RLS."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .modelos import Base


def criar_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _fk(conexao, _):  # SQLite só aplica chaves estrangeiras se pedirmos
            conexao.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True)


def criar_tabelas(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def fabrica_de_sessoes(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def definir_fazenda(sessao: Session, fazenda_id: str) -> None:
    """Em PostgreSQL, limita a transação às linhas desta fazenda (RNF07)."""
    if sessao.get_bind().dialect.name == "postgresql":
        sessao.execute(text("SELECT set_config('app.fazenda_id', :f, true)"), {"f": fazenda_id})


@contextmanager
def transacao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    with fabrica() as sessao, sessao.begin():
        yield sessao
