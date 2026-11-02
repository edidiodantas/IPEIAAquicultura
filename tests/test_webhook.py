import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from ipeia.api.app import criar_app
from ipeia.config import Configuracao
from ipeia.whatsapp.mensagens import extrair_mensagens

SEGREDO = "segredo-de-teste"


def payload(*mensagens):
    return {"object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": list(mensagens)}}]}]}


TEXTO = {"from": "5584999990000", "id": "wamid.A", "timestamp": "1793700000", "type": "text",
         "text": {"body": "30 kg no tanque 3"}}
AUDIO = {"from": "5584999990000", "id": "wamid.B", "timestamp": "1793700000", "type": "audio",
         "audio": {"id": "midia1", "mime_type": "audio/ogg; codecs=opus"}}
BOTAO = {"from": "5584999990000", "id": "wamid.C", "timestamp": "1793700000", "type": "interactive",
         "interactive": {"type": "button_reply", "button_reply": {"id": "confirmar:abc", "title": "Confirmar"}}}


def cliente():
    fila = []

    class Fila:
        def enfileirar(self, m):
            fila.append(m)

    cfg = Configuracao(_env_file=None, whatsapp_app_secret=SEGREDO, whatsapp_verify_token="tok")
    return TestClient(criar_app(cfg, Fila())), fila


def assinar(corpo: bytes) -> str:
    return "sha256=" + hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest()


def test_verificacao_da_meta():
    c, _ = cliente()
    r = c.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "tok",
                                           "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    r = c.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                           "hub.challenge": "42"})
    assert r.status_code == 403


def test_recebe_e_enfileira():
    c, fila = cliente()
    corpo = json.dumps(payload(TEXTO, AUDIO, BOTAO)).encode()
    r = c.post("/webhook/whatsapp", content=corpo, headers={"X-Hub-Signature-256": assinar(corpo)})
    assert r.status_code == 200 and r.json() == {"recebidas": 3}
    assert [m.tipo for m in fila] == ["text", "audio", "interactive"]


def test_assinatura_invalida():
    c, fila = cliente()
    corpo = json.dumps(payload(TEXTO)).encode()
    r = c.post("/webhook/whatsapp", content=corpo, headers={"X-Hub-Signature-256": "sha256=errado"})
    assert r.status_code == 401 and fila == []


def test_parse():
    texto, audio, botao = extrair_mensagens(payload(TEXTO, AUDIO, BOTAO))
    assert texto.texto == "30 kg no tanque 3"
    assert audio.media_id == "midia1"
    assert botao.botao_id == "confirmar:abc"
    assert texto.recebida_em.year == 2026
    # Status de entrega (sem "messages") são ignorados.
    assert extrair_mensagens({"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}) == []
