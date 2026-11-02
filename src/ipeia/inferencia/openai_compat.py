"""Adaptador HTTP para servidores compatíveis com a API da OpenAI.

Serve para todas as opções de hospedagem discutidas em docs/arquitetura.md:
vLLM local ou no Hetzner (`vllm serve ...`), vLLM no Modal (endpoint web) e
APIs por token que exponham o Amadeus-Verbo. Só muda a URL e a chave.
"""

import json
from typing import Any

import httpx

from .base import VOCABULARIO_AQUICOLA, Transcricao


class ErroInferencia(RuntimeError):
    pass


class ModeloOpenAICompat:
    def __init__(self, base_url: str, modelo: str, api_key: str = "", timeout_s: float = 180.0,
                 semente: int = 42, cliente: httpx.Client | None = None):
        self.modelo = modelo
        self.semente = semente
        cabecalhos = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = cliente or httpx.Client(base_url=base_url.rstrip("/"), headers=cabecalhos,
                                             timeout=timeout_s)

    def gerar_json(self, sistema: str, usuario: str, esquema: dict[str, Any]) -> dict[str, Any]:
        corpo = {
            "model": self.modelo,
            "messages": [
                # O prompt de sistema vem primeiro e não muda entre perguntas:
                # é o prefixo que o vLLM mantém em KV-Cache (RNF05).
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "temperature": 0.0,
            "seed": self.semente,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "saida", "schema": esquema, "strict": True},
            },
        }
        resposta = self._http.post("/chat/completions", json=corpo)
        if resposta.status_code >= 400:
            raise ErroInferencia(f"LLM respondeu {resposta.status_code}: {resposta.text[:300]}")
        conteudo = resposta.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(conteudo)
        except json.JSONDecodeError as exc:
            raise ErroInferencia(f"LLM não devolveu JSON válido: {conteudo[:300]}") from exc


class TranscritorOpenAICompat:
    """Endpoint /audio/transcriptions (ex.: faster-whisper servido no Modal)."""

    def __init__(self, base_url: str, modelo: str, api_key: str = "", timeout_s: float = 120.0,
                 cliente: httpx.Client | None = None):
        self.modelo = modelo
        cabecalhos = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = cliente or httpx.Client(base_url=base_url.rstrip("/"), headers=cabecalhos,
                                             timeout=timeout_s)

    def transcrever(self, audio: bytes, mime: str = "audio/ogg") -> Transcricao:
        resposta = self._http.post(
            "/audio/transcriptions",
            files={"file": ("audio", audio, mime)},
            data={"model": self.modelo, "language": "pt", "prompt": VOCABULARIO_AQUICOLA,
                  "response_format": "verbose_json"},
        )
        if resposta.status_code >= 400:
            raise ErroInferencia(f"Transcrição respondeu {resposta.status_code}")
        dados = resposta.json()
        segmentos = dados.get("segments") or []
        if segmentos:
            # avg_logprob perto de 0 indica alta confiança; convertemos para 0..1.
            import math
            media = sum(s.get("avg_logprob", 0.0) for s in segmentos) / len(segmentos)
            confianca = max(0.0, min(1.0, math.exp(media)))
        else:
            confianca = 1.0 if dados.get("text") else 0.0
        return Transcricao(texto=dados.get("text", "").strip(), confianca=confianca)
