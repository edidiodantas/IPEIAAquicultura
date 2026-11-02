"""O mock precisa entender frases típicas para os testes de fluxo fazerem sentido."""

from ipeia.inferencia.esquema import esquema_json
from ipeia.inferencia.mock import ModeloMock
from ipeia.manejo.esquemas import SaidaExtracao
from ipeia.manejo.extracao import extrair_manejo
from ipeia.roteamento import Intencao, rotear


def test_esquema_tem_titulo_e_e_fechado():
    esquema = esquema_json(SaidaExtracao)
    assert esquema["title"] == "extracao_manejo"
    assert esquema["additionalProperties"] is False


def test_extracao_varios_tanques():
    itens = extrair_manejo(ModeloMock(), "No tanque 3 dei 30 kg, no tanque da entrada meio saco às 7h")
    assert [(i.tanque, i.quantidade_racao, i.unidade_racao) for i in itens] == [
        ("tanque 3", 30, "kg"), ("tanque da entrada", 0.5, "saco")]
    assert itens[0].hora_manejo == "07:00"


def test_extracao_mortalidade():
    (item,) = extrair_manejo(ModeloMock(), "Tanque 2: 20 quilos de ração 4 mm, morreram 5 peixes ontem")
    assert item.mortalidade == 5 and item.tipo_racao == "4 mm" and item.dias_atras == 1


def test_roteamento_misto():
    segmentos = rotear(ModeloMock(), "Dei 20 kg no tanque 2. Qual o oxigênio mínimo para tilápia?")
    assert [s.intencao for s in segmentos] == [Intencao.manejo, Intencao.consulta]
