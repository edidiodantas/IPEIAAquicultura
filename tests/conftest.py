"""Fixtures comuns: banco SQLite em arquivo temporário, adaptadores mock e fazenda demo."""

from datetime import timedelta
from itertools import count

import pytest

from ipeia.banco.sessao import criar_engine, criar_tabelas, fabrica_de_sessoes, transacao
from ipeia.cadastro import TELEFONE_DEMO, criar_fazenda_demo
from ipeia.cag.acervo import carregar_acervo
from ipeia.config import RAIZ_PROJETO, Configuracao
from ipeia.inferencia.mock import ModeloMock, TranscritorMock
from ipeia.manejo.limites import carregar_limites
from ipeia.orquestrador import Orquestrador
from ipeia.tempo import agora_utc
from ipeia.whatsapp.cliente import ClienteMock
from ipeia.whatsapp.mensagens import MensagemEntrada


@pytest.fixture
def cfg(tmp_path):
    return Configuracao(_env_file=None, database_url=f"sqlite:///{tmp_path / 'teste.db'}")


@pytest.fixture
def limites():
    return carregar_limites(RAIZ_PROJETO / "config" / "limites.toml")


@pytest.fixture
def acervo():
    return carregar_acervo(RAIZ_PROJETO / "acervo")


@pytest.fixture
def fabrica(cfg):
    engine = criar_engine(cfg.database_url)
    criar_tabelas(engine)
    return fabrica_de_sessoes(engine)


@pytest.fixture
def fazenda_id(fabrica):
    with transacao(fabrica) as s:
        return criar_fazenda_demo(s).id


@pytest.fixture
def whatsapp():
    return ClienteMock()


@pytest.fixture
def orq(cfg, fabrica, fazenda_id, whatsapp, limites, acervo):
    return Orquestrador(fabrica, cfg, ModeloMock(), TranscritorMock(), whatsapp, limites, acervo)


class Produtor:
    """Simula o produtor mandando mensagens e tocando botões."""

    def __init__(self, orq: Orquestrador, whatsapp: ClienteMock, telefone: str = TELEFONE_DEMO):
        self.orq, self.whatsapp, self.telefone = orq, whatsapp, telefone
        self._ids = count(1)

    def _base(self, atraso_s: int = 0):
        return dict(wa_message_id=f"wamid.{self.telefone}.{next(self._ids)}", telefone=self.telefone,
                    recebida_em=agora_utc() - timedelta(seconds=atraso_s))

    def _enviar(self, entrada: MensagemEntrada):
        inicio = len(self.whatsapp.enviadas)
        self.orq.processar(entrada)
        return self.whatsapp.enviadas[inicio:]

    def texto(self, texto: str):
        return self._enviar(MensagemEntrada(tipo="text", texto=texto, **self._base()))

    def audio(self, conteudo: str):
        media = f"media-{next(self._ids)}"
        self.whatsapp.midias[media] = conteudo.encode()
        return self._enviar(MensagemEntrada(tipo="audio", media_id=media, mime="audio/ogg", **self._base()))

    def botao(self, botao_id: str):
        return self._enviar(MensagemEntrada(tipo="interactive", botao_id=botao_id, **self._base()))

    def tocar(self, titulo: str):
        """Toca o botão com esse título na última mensagem com botões."""
        ultima = next(m for m in reversed(self.whatsapp.enviadas) if m.botoes)
        return self.botao(next(b.id for b in ultima.botoes if b.titulo == titulo))


@pytest.fixture
def produtor(orq, whatsapp):
    return Produtor(orq, whatsapp)
