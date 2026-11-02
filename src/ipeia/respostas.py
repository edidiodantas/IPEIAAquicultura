"""Resposta que um fluxo quer mandar ao produtor.

Os fluxos (manejo, consulta, confirmação) devolvem `Resposta` em vez de chamar
o WhatsApp diretamente. Isso deixa cada fluxo testável sem rede e concentra o
envio num só lugar (o orquestrador).
"""

from dataclasses import dataclass, field

from .whatsapp.cliente import Botao


@dataclass
class Resposta:
    texto: str
    botoes: list[Botao] = field(default_factory=list)


def botoes_confirmacao(pendencia_id: str) -> list[Botao]:
    """Os três botões do RF02. O id carrega a ação e a pendência."""
    return [
        Botao(f"confirmar:{pendencia_id}", "Confirmar"),
        Botao(f"corrigir:{pendencia_id}", "Corrigir"),
        Botao(f"cancelar:{pendencia_id}", "Cancelar"),
    ]
