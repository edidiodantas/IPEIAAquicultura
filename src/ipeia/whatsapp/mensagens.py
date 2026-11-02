"""Conversão do JSON do webhook da Meta em mensagens simples."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from ..tempo import de_timestamp_whatsapp


@dataclass(frozen=True)
class MensagemEntrada:
    wa_message_id: str
    telefone: str
    recebida_em: datetime
    tipo: Literal["text", "audio", "interactive"]
    texto: str | None = None
    media_id: str | None = None
    mime: str | None = None
    botao_id: str | None = None  # id do botão de resposta (ex.: "confirmar:<pendencia>")


def extrair_mensagens(payload: dict[str, Any]) -> list[MensagemEntrada]:
    """Ignora status de entrega e tipos não suportados (imagem, figurinha...)."""
    resultado: list[MensagemEntrada] = []
    for entrada in payload.get("entry", []):
        for mudanca in entrada.get("changes", []):
            for m in mudanca.get("value", {}).get("messages", []) or []:
                base = dict(wa_message_id=m["id"], telefone=m["from"],
                            recebida_em=de_timestamp_whatsapp(m["timestamp"]))
                tipo = m.get("type")
                if tipo == "text":
                    resultado.append(MensagemEntrada(tipo="text", texto=m["text"]["body"], **base))
                elif tipo == "audio":
                    resultado.append(MensagemEntrada(tipo="audio", media_id=m["audio"]["id"],
                                                     mime=m["audio"].get("mime_type"), **base))
                elif tipo == "interactive" and m.get("interactive", {}).get("type") == "button_reply":
                    resposta = m["interactive"]["button_reply"]
                    resultado.append(MensagemEntrada(tipo="interactive", botao_id=resposta["id"],
                                                     texto=resposta.get("title"), **base))
                elif tipo == "button":  # resposta a botão de modelo de mensagem
                    resultado.append(MensagemEntrada(tipo="interactive", botao_id=m["button"].get("payload"),
                                                     texto=m["button"].get("text"), **base))
    return resultado
