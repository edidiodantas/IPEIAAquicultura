"""Orquestrador: recebe uma mensagem do WhatsApp e despacha para o fluxo certo.

Passo a passo de `processar`:
  1. Identifica a fazenda pelo número e ativa o RLS dela; números não cadastrados recebem um aviso.
  2. Descarta mensagem repetida pelo ID do WhatsApp (RNF06).
  3. Pede o consentimento da LGPD no primeiro contato (RNF07).
  4. Botões vão para a confirmação (RF02).
  5. Áudio é transcrito (RF01); baixa confiança pede para repetir.
  6. Justificativa pendente e cadastro de apelido são tratados antes do roteador.
  7. O roteador (RF08) divide a mensagem e cada trecho vai ao seu fluxo.

Toda a mensagem roda numa única transação: se algo falhar, nada fica pela metade.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .banco.modelos import Fazenda, MensagemRecebida, Usuario
from .banco.sessao import definir_fazenda
from .cag.acervo import Acervo
from .cag.servico import processar_consulta
from .config import Configuracao
from .confirmacao.servico import (pendencia_aguardando_justificativa, registrar_justificativa,
                                  tratar_botao)
from .contexto import Contexto
from .inferencia.base import ModeloLinguagem, Transcritor
from .manejo.apelidos import cadastrar_apelido, interpretar_cadastro
from .manejo.correcao import processar_correcao
from .manejo.limites import TabelaLimites
from .manejo.servico import processar_manejo
from .respostas import Resposta
from .roteamento import Intencao, rotear
from .tempo import agora_utc
from .whatsapp.cliente import Botao, ClienteWhatsApp
from .whatsapp.mensagens import MensagemEntrada

log = logging.getLogger(__name__)

TEXTO_CONSENTIMENTO = (
    "Olá! Sou o assistente da IPEIA Aquicultura. Para registrar o manejo da sua fazenda, "
    "guardo seus áudios por até 90 dias e os dados da produção num banco protegido. "
    "Seus dados não são usados para treinar modelos de IA de terceiros. Você concorda?"
)
TEXTO_AJUDA = (
    "Posso registrar o manejo (ex.: “30 kg de ração no tanque 3, 2 mortos”) ou tirar dúvidas "
    "técnicas com base nos manuais (ex.: “qual o oxigênio mínimo para tilápia?”)."
)


@dataclass
class Orquestrador:
    fabrica_sessoes: sessionmaker[Session]
    cfg: Configuracao
    modelo: ModeloLinguagem
    transcritor: Transcritor
    whatsapp: ClienteWhatsApp
    limites: TabelaLimites
    acervo: Acervo

    def processar(self, entrada: MensagemEntrada) -> None:
        """Processa uma mensagem e envia as respostas ao produtor."""
        respostas: list[Resposta] = []
        with self.fabrica_sessoes() as sessao, sessao.begin():
            respostas = self._processar(sessao, entrada)
        # Envia só depois do commit: o produtor nunca vê um registro que não foi gravado.
        for r in respostas:
            if r.botoes:
                self.whatsapp.enviar_botoes(entrada.telefone, r.texto, r.botoes)
            else:
                self.whatsapp.enviar_texto(entrada.telefone, r.texto)

    def _processar(self, sessao: Session, entrada: MensagemEntrada) -> list[Resposta]:
        # 1. Quem é? A tabela de usuários fica fora do RLS justamente para isso.
        #    A fazenda é definida antes de qualquer outra leitura ou escrita, para
        #    que as políticas de RLS do PostgreSQL já valham (RNF07).
        usuario = sessao.scalar(select(Usuario).where(Usuario.telefone == entrada.telefone))
        if usuario is not None:
            definir_fazenda(sessao, usuario.fazenda_id)

        # 2. Deduplicação (o WhatsApp reenvia o webhook se demorarmos a responder, RNF06).
        if sessao.scalar(select(MensagemRecebida.id).where(
                MensagemRecebida.wa_message_id == entrada.wa_message_id)):
            log.info("mensagem repetida ignorada: %s", entrada.wa_message_id)
            return []

        # Registro da mensagem para auditoria (RNF09).
        registro = MensagemRecebida(
            wa_message_id=entrada.wa_message_id, telefone=entrada.telefone, tipo=entrada.tipo,
            recebida_em=entrada.recebida_em, media_id=entrada.media_id, texto=entrada.texto,
            fazenda_id=usuario.fazenda_id if usuario else None,
        )
        sessao.add(registro)
        if usuario is None:
            registro.processada_em = agora_utc()
            return [Resposta("Este número não está cadastrado. Peça ao responsável pela fazenda "
                             "para incluir você.")]
        fazenda = sessao.get(Fazenda, usuario.fazenda_id)
        sessao.flush()  # gera o ID da mensagem, usado nos lançamentos

        try:
            return self._despachar(Contexto(sessao, fazenda, usuario, registro, self.cfg, self.modelo,
                                            self.limites, self.acervo), entrada)
        finally:
            registro.processada_em = agora_utc()

    def _despachar(self, ctx: Contexto, entrada: MensagemEntrada) -> list[Resposta]:
        usuario = ctx.usuario

        # 3. Consentimento LGPD (RNF07).
        if usuario.consentiu_em is None:
            if entrada.botao_id == "consentimento:sim":
                usuario.consentiu_em = agora_utc()
                return [Resposta("Obrigado! " + TEXTO_AJUDA)]
            if entrada.botao_id == "consentimento:nao":
                return [Resposta("Tudo bem. Sem o consentimento não consigo registrar dados. "
                                 "Se mudar de ideia, mande uma mensagem.")]
            return [Resposta(TEXTO_CONSENTIMENTO, [Botao("consentimento:sim", "Concordo"),
                                                   Botao("consentimento:nao", "Não concordo")])]

        # 4. Botões de confirmação (RF02).
        if entrada.tipo == "interactive" and entrada.botao_id:
            return [tratar_botao(ctx.sessao, ctx.fazenda.id, usuario.telefone, entrada.botao_id)]

        # 5. Áudio -> texto (RF01).
        texto = entrada.texto or ""
        if entrada.tipo == "audio":
            texto, erro = self._transcrever(ctx, entrada)
            if erro:
                return [erro]
        if not texto.strip():
            return [Resposta(TEXTO_AJUDA)]

        # 6a. Texto que responde a um pedido de justificativa (alerta do RF05).
        pendente = pendencia_aguardando_justificativa(ctx.sessao, ctx.fazenda.id, usuario.telefone)
        if pendente is not None:
            return [registrar_justificativa(ctx.sessao, pendente, usuario.telefone, texto)]

        # 6b. Cadastro de apelido pelo WhatsApp (RF04): "apelido tanque do fundo = T3".
        if cadastro := interpretar_cadastro(texto):
            tanque = cadastrar_apelido(ctx.sessao, ctx.fazenda.id, *cadastro)
            if tanque is None:
                return [Resposta(f"Não achei o tanque “{cadastro[1]}”.")]
            return [Resposta(f"Pronto: “{cadastro[0]}” agora é o tanque {tanque.codigo}.")]

        # 7. Roteamento de intenção (RF08): o código decide o fluxo, não o modelo.
        segmentos = rotear(ctx.modelo, texto)
        ctx.mensagem.intencoes = {"segmentos": [s.model_dump(mode="json") for s in segmentos]}
        respostas = []
        for seg in segmentos:
            if seg.intencao == Intencao.manejo:
                respostas.append(processar_manejo(ctx, seg.texto))
            elif seg.intencao == Intencao.consulta:
                respostas.append(processar_consulta(ctx, seg.texto))
            elif seg.intencao == Intencao.correcao:
                respostas.append(processar_correcao(ctx, seg.texto))
        if not respostas:  # só "outro": em vez de adivinhar, explica o que sabe fazer
            respostas.append(Resposta(TEXTO_AJUDA))
        return respostas

    def _transcrever(self, ctx: Contexto, entrada: MensagemEntrada) -> tuple[str, Resposta | None]:
        audio = self.whatsapp.baixar_midia(entrada.media_id)
        transcricao = self.transcritor.transcrever(audio, entrada.mime or "audio/ogg")
        ctx.mensagem.texto = transcricao.texto
        ctx.mensagem.confianca_transcricao = transcricao.confianca
        if transcricao.confianca < self.cfg.stt_confianca_minima or not transcricao.texto:
            return "", Resposta("Não consegui entender bem o áudio. Pode repetir mais devagar "
                                "ou digitar a mensagem?")
        return transcricao.texto, None
