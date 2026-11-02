"""Envio de mensagens ao WhatsApp. `ClienteMock` guarda tudo em memória."""

from dataclasses import dataclass, field
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Botao:
    id: str
    titulo: str  # até 20 caracteres no WhatsApp


class ClienteWhatsApp(Protocol):
    def enviar_texto(self, para: str, texto: str) -> None: ...

    def enviar_botoes(self, para: str, texto: str, botoes: list[Botao]) -> None:
        """Mensagem com até 3 botões de resposta (RF02)."""
        ...

    def baixar_midia(self, media_id: str) -> bytes: ...


@dataclass
class MensagemEnviada:
    para: str
    texto: str
    botoes: list[Botao] = field(default_factory=list)


class ClienteMock:
    def __init__(self, midias: dict[str, bytes] | None = None):
        self.enviadas: list[MensagemEnviada] = []
        self.midias: dict[str, bytes] = midias or {}

    def enviar_texto(self, para: str, texto: str) -> None:
        self.enviadas.append(MensagemEnviada(para, texto))

    def enviar_botoes(self, para: str, texto: str, botoes: list[Botao]) -> None:
        self.enviadas.append(MensagemEnviada(para, texto, list(botoes)))

    def baixar_midia(self, media_id: str) -> bytes:
        return self.midias[media_id]


class ClienteCloudAPI:
    """WhatsApp Cloud API (graph.facebook.com)."""

    def __init__(self, token: str, phone_number_id: str, versao: str = "v21.0",
                 cliente: httpx.Client | None = None):
        self._phone = phone_number_id
        self._http = cliente or httpx.Client(base_url=f"https://graph.facebook.com/{versao}",
                                             headers={"Authorization": f"Bearer {token}"}, timeout=30)

    def _enviar(self, corpo: dict) -> None:
        r = self._http.post(f"/{self._phone}/messages", json={"messaging_product": "whatsapp", **corpo})
        r.raise_for_status()

    def enviar_texto(self, para: str, texto: str) -> None:
        self._enviar({"to": para, "type": "text", "text": {"body": texto[:4096]}})

    def enviar_botoes(self, para: str, texto: str, botoes: list[Botao]) -> None:
        self._enviar({
            "to": para,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto[:1024]},
                "action": {"buttons": [{"type": "reply", "reply": {"id": b.id, "title": b.titulo[:20]}}
                                       for b in botoes[:3]]},
            },
        })

    def baixar_midia(self, media_id: str) -> bytes:
        info = self._http.get(f"/{media_id}")
        info.raise_for_status()
        arquivo = self._http.get(info.json()["url"])
        arquivo.raise_for_status()
        return arquivo.content


def criar_cliente(cfg) -> ClienteWhatsApp:
    if cfg.whatsapp_backend == "cloud":
        return ClienteCloudAPI(cfg.whatsapp_token, cfg.whatsapp_phone_number_id, cfg.whatsapp_api_versao)
    return ClienteMock()
