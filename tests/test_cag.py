"""Barreira de citação (RNF03) e aviso legal (RF07)."""

from ipeia.cag.consulta import responder
from ipeia.cag.textos import AVISO_LEGAL, FRASE_NAO_ENCONTRADO
from ipeia.inferencia.mock import ModeloMock


class ModeloQueInventa(ModeloMock):
    """Simula o modelo alucinando: responde com uma citação que não existe no acervo."""

    def gerar_json(self, sistema, usuario, esquema):
        if esquema.get("title") == "resposta_tecnica":
            return {"encontrado": True, "resposta": "Use 2 g/L de sal por 3 dias.",
                    "citacao_literal": "aplicar sal grosso na dose de 2 g/L durante três dias"}
        return super().gerar_json(sistema, usuario, esquema)


def test_resposta_com_citacao_e_aviso(acervo):
    r = responder(ModeloMock(), acervo, "Qual o oxigênio dissolvido mínimo para tilápia?")
    assert r.verificada and r.bloco == "exemplo-qualidade-agua"
    assert "p. 1" in r.texto and r.texto.endswith(AVISO_LEGAL)
    assert r.versao_acervo == "exemplo-qualidade-agua@2026.11-exemplo"


def test_citacao_inventada_vira_frase_padrao(acervo):
    r = responder(ModeloQueInventa(), acervo, "Como tratar a mortalidade com sal?")
    assert r.texto == FRASE_NAO_ENCONTRADO and not r.verificada
    assert r.citacao  # guardamos o que o modelo tentou citar, para auditoria


def test_assunto_fora_do_acervo(acervo):
    r = responder(ModeloMock(), acervo, "Qual o preço do milho na bolsa?")
    assert r.texto == FRASE_NAO_ENCONTRADO


def test_bloco_cabe_na_janela(acervo):
    assert acervo.verificar_tamanho(32768) == []


def test_citacao_ignora_espacos_e_maiusculas(acervo):
    bloco = acervo.blocos["exemplo-sanidade"]
    assert bloco.localizar("LOTES novos devem passar   por quarentena em tanque separado").pagina == "2"
    assert bloco.localizar("curto") is None
