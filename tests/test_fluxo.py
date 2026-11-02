"""Testes ponta a ponta com o orquestrador, o banco SQLite e os adaptadores mock."""

from datetime import timedelta

from sqlalchemy import func, select

from ipeia.banco.modelos import (ConsultaTecnica, Lancamento, Lote, Pendencia, StatusLancamento,
                                 StatusPendencia, Tanque, TipoLancamento, Usuario)
from ipeia.banco.sessao import transacao
from ipeia.cag.textos import AVISO_LEGAL, FRASE_NAO_ENCONTRADO
from ipeia.confirmacao.servico import expirar_pendencias
from ipeia.tempo import agora_utc

from conftest import Produtor


def lancamentos(fabrica, status=None):
    with transacao(fabrica) as s:
        q = select(Lancamento)
        if status:
            q = q.where(Lancamento.status == status)
        return list(s.scalars(q))


def lote_de(fabrica, codigo):
    with transacao(fabrica) as s:
        return s.scalar(select(Lote).join(Tanque).where(Tanque.codigo == codigo))


def test_manejo_confirmado(produtor, fabrica):
    (resumo,) = produtor.texto("Dei 8 kg de ração no tanque da entrada e meio saco no tanque do meio, "
                               "morreram 3 no tanque do meio.")
    assert [b.titulo for b in resumo.botoes] == ["Confirmar", "Corrigir", "Cancelar"]
    assert "T1: 8 kg" in resumo.texto and "T2: 12,5 kg de ração, 3 mortos" in resumo.texto
    assert lancamentos(fabrica, StatusLancamento.confirmado) == []  # nada definitivo antes do botão

    (ok,) = produtor.tocar("Confirmar")
    assert ok.texto == "✅ Registrado."
    confirmados = lancamentos(fabrica, StatusLancamento.confirmado)
    assert sorted(l.racao_kg for l in confirmados) == [8, 12.5]
    assert all(l.confirmado_por == produtor.telefone for l in confirmados)
    assert lote_de(fabrica, "T2").quantidade_atual == 1497


def test_audio_transcrito(produtor, fabrica):
    (resumo,) = produtor.audio("No tanque 3 dei 2 kg às 7h")
    assert "T3: 2 kg" in resumo.texto and "às 07:00" in resumo.texto
    produtor.tocar("Confirmar")
    (l,) = lancamentos(fabrica, StatusLancamento.confirmado)
    assert l.json_extraido["itens"][0]["tanque"] == "tanque 3"  # trilha de auditoria (RNF09)
    assert l.recebido_em != l.manejo_em  # três horários (RNF06)


def test_audio_com_baixa_confianca(produtor, fabrica):
    (r,) = produtor.audio("#baixa# trinta quilo no tanque")
    assert "repetir" in r.texto
    assert lancamentos(fabrica) == []


def test_bloqueio_nao_cria_pendencia(produtor, fabrica):
    (r,) = produtor.texto("100 kg no tanque 3")  # 200% da biomassa de 50 kg
    assert r.texto.startswith("🚫") and not r.botoes
    assert lancamentos(fabrica) == []


def test_bloqueio_de_um_tanque_barra_a_mensagem(produtor, fabrica):
    (r,) = produtor.texto("No tanque 1 dei 5 kg, no tanque 3 dei 100 kg")
    assert r.texto.startswith("🚫") and "T3" in r.texto
    assert lancamentos(fabrica) == []


def test_alerta_exige_justificativa(produtor, fabrica):
    (resumo,) = produtor.texto("12 kg no tanque 1")  # 6% da biomassa de 200 kg; alerta acima de 5%
    assert "Fora do usual" in resumo.texto
    (pedido,) = produtor.tocar("Confirmar")
    assert "motivo" in pedido.texto
    assert lancamentos(fabrica, StatusLancamento.confirmado) == []
    (ok,) = produtor.texto("Biometria mostrou que cresceram, vou ajustar o lote")
    assert ok.texto.startswith("✅")
    (l,) = lancamentos(fabrica, StatusLancamento.confirmado)
    assert l.justificativa.startswith("Biometria")


def test_soma_do_dia_entre_mensagens(produtor):
    produtor.texto("8 kg no tanque 1")
    produtor.tocar("Confirmar")
    (resumo,) = produtor.texto("4 kg no tanque 1")  # 12 kg no dia = 6%: alerta
    assert "12 kg de ração no dia" in resumo.texto


def test_cancelar_e_corrigir(produtor, fabrica):
    produtor.texto("5 kg no tanque 2")
    (r,) = produtor.tocar("Cancelar")
    assert "Cancelado" in r.texto
    produtor.texto("6 kg no tanque 2")
    (r,) = produtor.tocar("Corrigir")
    assert "Envie de novo" in r.texto
    assert {l.status for l in lancamentos(fabrica)} == {StatusLancamento.cancelado}
    (r,) = produtor.tocar("Confirmar")  # botão antigo não ressuscita a pendência
    assert "já foi cancelada" in r.texto


def test_mensagem_repetida_e_ignorada(orq, whatsapp, fabrica):
    from ipeia.whatsapp.mensagens import MensagemEntrada

    m = MensagemEntrada(wa_message_id="wamid.X", telefone="5584999990000", recebida_em=agora_utc(),
                        tipo="text", texto="5 kg no tanque 2")
    orq.processar(m)
    orq.processar(m)
    assert len(whatsapp.enviadas) == 1
    assert len(lancamentos(fabrica)) == 1


def test_expiracao(produtor, fabrica):
    produtor.texto("5 kg no tanque 2")
    with transacao(fabrica) as s:
        assert expirar_pendencias(s, agora_utc() + timedelta(hours=25)) == 1
        assert s.scalar(select(Pendencia.status)) == StatusPendencia.expirada
    (r,) = produtor.tocar("Confirmar")
    assert "já foi expirada" in r.texto


def test_expiracao_ao_tocar(produtor, fabrica):
    produtor.texto("5 kg no tanque 2")
    with transacao(fabrica) as s:
        s.scalar(select(Pendencia)).expira_em = agora_utc() - timedelta(minutes=1)
    (r,) = produtor.tocar("Confirmar")
    assert "expirou" in r.texto


def test_outro_numero_nao_confirma(produtor, orq, whatsapp, fabrica, fazenda_id):
    produtor.texto("5 kg no tanque 2")
    with transacao(fabrica) as s:
        s.add(Usuario(fazenda_id=fazenda_id, telefone="5584888880000", consentiu_em=agora_utc()))
    botao = whatsapp.enviadas[-1].botoes[0].id
    (r,) = Produtor(orq, whatsapp, "5584888880000").botao(botao)
    assert r.texto == "Não encontrei esse lançamento."


def test_numero_nao_cadastrado(orq, whatsapp):
    (r,) = Produtor(orq, whatsapp, "5511000000000").texto("10 kg no tanque 1")
    assert "não está cadastrado" in r.texto


def test_consentimento_no_primeiro_contato(orq, whatsapp, fabrica, fazenda_id):
    with transacao(fabrica) as s:
        s.add(Usuario(fazenda_id=fazenda_id, telefone="5584777770000"))
    novo = Produtor(orq, whatsapp, "5584777770000")
    (r,) = novo.texto("10 kg no tanque 1")
    assert "concorda" in r.texto and r.botoes[0].id == "consentimento:sim"
    assert lancamentos(fabrica) == []
    novo.tocar("Concordo")
    (r,) = novo.texto("5 kg no tanque 1")
    assert r.botoes  # agora vira lançamento


def test_consulta_tecnica(produtor, fabrica):
    (r,) = produtor.texto("Qual o oxigênio dissolvido mínimo para tilápia?")
    assert "4 mg/L" in r.texto and r.texto.endswith(AVISO_LEGAL)
    with transacao(fabrica) as s:
        c = s.scalar(select(ConsultaTecnica))
        assert c.citacao_verificada and c.versao_acervo.startswith("exemplo-qualidade-agua@")


def test_consulta_sem_resposta(produtor):
    (r,) = produtor.texto("Qual o preço do milho na bolsa?")
    assert r.texto == FRASE_NAO_ENCONTRADO


def test_mensagem_mista(produtor):
    respostas = produtor.texto("Dei 5 kg no tanque 2. Qual o oxigênio mínimo para tilápia?")
    assert len(respostas) == 2
    assert respostas[0].botoes and AVISO_LEGAL in respostas[1].texto


def test_tanque_desconhecido_e_cadastro_de_apelido(produtor):
    (r,) = produtor.texto("5 kg no tanque da represa")
    assert "não conheço" in r.texto and "apelido" in r.texto
    (r,) = produtor.texto("apelido tanque da represa = T2")
    assert "T2" in r.texto
    (r,) = produtor.texto("5 kg no tanque da represa")
    assert r.botoes and "T2: 5 kg" in r.texto


def test_correcao_gera_estorno(produtor, fabrica):
    produtor.texto("No tanque 2 dei 20 kg, morreram 4")  # 2,7% da biomassa: sem alerta
    produtor.tocar("Confirmar")
    assert lote_de(fabrica, "T2").quantidade_atual == 1496

    (resumo,) = produtor.texto("O de hoje no tanque 2 foi 15 kg, não 20.")
    assert "Estornar" in resumo.texto
    produtor.tocar("Confirmar")

    with transacao(fabrica) as s:
        todos = list(s.scalars(select(Lancamento).order_by(Lancamento.processado_em)))
        original, estorno, novo = todos
        assert original.status == StatusLancamento.confirmado  # o original nunca é apagado
        assert estorno.tipo == TipoLancamento.estorno and estorno.estorna_id == original.id
        assert novo.racao_kg == 15 and novo.mortalidade == 4
    assert lote_de(fabrica, "T2").quantidade_atual == 1496  # devolveu 4 e tirou 4

    # Uma nova correção atua sobre o lançamento corrigido, não sobre o original.
    produtor.texto("Cancela o de hoje no tanque 2")
    produtor.tocar("Confirmar")
    with transacao(fabrica) as s:
        assert s.scalar(select(func.count()).select_from(Lancamento)
                        .where(Lancamento.tipo == TipoLancamento.estorno)) == 2
    assert lote_de(fabrica, "T2").quantidade_atual == 1500


def test_correcao_sem_lancamento(produtor):
    (r,) = produtor.texto("Corrige o de ontem no tanque 1, foi 5 kg")
    assert "Não achei" in r.texto
