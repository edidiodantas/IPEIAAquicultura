"""Dados de uma mensagem em processamento, passados de fluxo em fluxo."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .banco.modelos import Fazenda, MensagemRecebida, Usuario
from .cag.acervo import Acervo
from .config import Configuracao
from .inferencia.base import ModeloLinguagem
from .manejo.limites import TabelaLimites


@dataclass
class Contexto:
    sessao: Session            # transação aberta, já limitada à fazenda (RLS)
    fazenda: Fazenda
    usuario: Usuario
    mensagem: MensagemRecebida  # registro da mensagem (auditoria, RNF09)
    cfg: Configuracao
    modelo: ModeloLinguagem
    limites: TabelaLimites
    acervo: Acervo

    @property
    def peso_saco_kg(self) -> float:
        return self.fazenda.peso_saco_kg or self.limites.geral.peso_saco_kg_padrao
