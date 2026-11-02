"""O adaptador HTTP manda temperatura 0, semente fixa e o esquema JSON (RNF02)."""

import json

import httpx

from ipeia.inferencia.openai_compat import ModeloOpenAICompat


def test_chamada_deterministica_com_esquema():
    enviado = {}

    def responder(request: httpx.Request) -> httpx.Response:
        enviado.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"bloco": "nenhum"}'}}]})

    http = httpx.Client(base_url="http://vllm/v1", transport=httpx.MockTransport(responder))
    modelo = ModeloOpenAICompat("http://vllm/v1", "amadeus", cliente=http)
    esquema = {"title": "escolha_bloco", "type": "object"}
    assert modelo.gerar_json("sistema", "pergunta", esquema) == {"bloco": "nenhum"}
    assert enviado["temperature"] == 0.0 and enviado["seed"] == 42
    assert enviado["response_format"]["json_schema"]["schema"] == esquema
    assert enviado["messages"][0] == {"role": "system", "content": "sistema"}
