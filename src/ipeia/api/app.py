"""Aplicação FastAPI. Rode com: uvicorn ipeia.api.app:app --reload"""

import json
import logging

from fastapi import FastAPI, HTTPException, Query, Request, Response

from ..config import Configuracao, obter_configuracao
from ..fila import Fila, FilaEmThreads
from ..montagem import montar_orquestrador
from ..whatsapp.assinatura import assinatura_valida
from ..whatsapp.mensagens import extrair_mensagens

log = logging.getLogger(__name__)


def criar_app(cfg: Configuracao | None = None, fila: Fila | None = None) -> FastAPI:
    cfg = cfg or obter_configuracao()
    if fila is None:
        fila = FilaEmThreads(montar_orquestrador(cfg).processar)

    app = FastAPI(title="IPEIA Aquicultura")

    @app.get("/saude")
    def saude() -> dict:
        return {"status": "ok", "llm": cfg.llm_backend, "stt": cfg.stt_backend,
                "whatsapp": cfg.whatsapp_backend}

    @app.get("/webhook/whatsapp")
    def verificar(modo: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
                  desafio: str = Query(alias="hub.challenge")) -> Response:
        """Verificação feita pela Meta quando o webhook é cadastrado."""
        if modo == "subscribe" and token == cfg.whatsapp_verify_token:
            return Response(desafio, media_type="text/plain")
        raise HTTPException(status_code=403)

    @app.post("/webhook/whatsapp")
    async def receber(request: Request) -> dict:
        corpo = await request.body()
        if not assinatura_valida(corpo, request.headers.get("X-Hub-Signature-256"),
                                 cfg.whatsapp_app_secret):
            raise HTTPException(status_code=401, detail="assinatura inválida")
        try:
            payload = json.loads(corpo)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="JSON inválido") from exc
        # Só enfileira e responde 200 na hora; o processamento é assíncrono (RNF06).
        mensagens = extrair_mensagens(payload)
        for m in mensagens:
            fila.enfileirar(m)
        return {"recebidas": len(mensagens)}

    return app


# Instância usada pelo uvicorn. Criada sob demanda para não abrir o banco ao importar.
def __getattr__(nome: str):
    if nome == "app":
        global app
        app = criar_app()
        return app
    raise AttributeError(nome)
