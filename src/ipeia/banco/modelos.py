"""Modelos relacionais (RF09, RF10, RNF06, RNF07, RNF09).

Toda tabela com dados da fazenda tem `fazenda_id`, usado pelas políticas de
row-level security em `sql/rls_postgres.sql`. Lançamentos nunca são apagados:
uma correção grava um estorno ligado ao original (RF10).
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..tempo import agora_utc


def _uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True), dict[str, Any]: JSON}


class Fazenda(Base):
    __tablename__ = "fazendas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    nome: Mapped[str] = mapped_column(String(200))
    peso_saco_kg: Mapped[float] = mapped_column(Float, default=25.0)
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc)

    tanques: Mapped[list["Tanque"]] = relationship(back_populates="fazenda")


class Usuario(Base):
    """Número de WhatsApp autorizado a lançar dados de uma fazenda."""

    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    fazenda_id: Mapped[str] = mapped_column(ForeignKey("fazendas.id"), index=True)
    telefone: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(200), default="")
    consentiu_em: Mapped[datetime | None] = mapped_column(default=None)  # LGPD, RNF07

    fazenda: Mapped[Fazenda] = relationship()


class Tanque(Base):
    __tablename__ = "tanques"
    __table_args__ = (UniqueConstraint("fazenda_id", "codigo"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    fazenda_id: Mapped[str] = mapped_column(ForeignKey("fazendas.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(50))  # ex.: "T3"
    area_m2: Mapped[float | None] = mapped_column(Float, default=None)
    volume_m3: Mapped[float | None] = mapped_column(Float, default=None)

    fazenda: Mapped[Fazenda] = relationship(back_populates="tanques")
    apelidos: Mapped[list["ApelidoTanque"]] = relationship(back_populates="tanque")
    lotes: Mapped[list["Lote"]] = relationship(back_populates="tanque")


class ApelidoTanque(Base):
    """Dicionário de apelidos (RF04): "tanque da entrada" -> T1."""

    __tablename__ = "apelidos_tanque"
    __table_args__ = (UniqueConstraint("fazenda_id", "apelido"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    fazenda_id: Mapped[str] = mapped_column(ForeignKey("fazendas.id"), index=True)
    tanque_id: Mapped[str] = mapped_column(ForeignKey("tanques.id"))
    apelido: Mapped[str] = mapped_column(String(200))  # já normalizado

    tanque: Mapped[Tanque] = relationship(back_populates="apelidos")


class Lote(Base):
    __tablename__ = "lotes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    fazenda_id: Mapped[str] = mapped_column(ForeignKey("fazendas.id"), index=True)
    tanque_id: Mapped[str] = mapped_column(ForeignKey("tanques.id"))
    especie: Mapped[str] = mapped_column(String(50))  # chave em config/limites.toml
    fase: Mapped[str] = mapped_column(String(50))
    quantidade_inicial: Mapped[int] = mapped_column(Integer)
    quantidade_atual: Mapped[int] = mapped_column(Integer)
    peso_medio_g: Mapped[float] = mapped_column(Float)
    ativo: Mapped[bool] = mapped_column(default=True)
    povoado_em: Mapped[datetime] = mapped_column(default=agora_utc)

    tanque: Mapped[Tanque] = relationship(back_populates="lotes")

    @property
    def biomassa_kg(self) -> float:
        return self.quantidade_atual * self.peso_medio_g / 1000


class MensagemRecebida(Base):
    """Cada mensagem do WhatsApp, uma vez só (deduplicação pelo ID, RNF06)."""

    __tablename__ = "mensagens_recebidas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    wa_message_id: Mapped[str] = mapped_column(String(200), unique=True)
    fazenda_id: Mapped[str | None] = mapped_column(ForeignKey("fazendas.id"), index=True)
    telefone: Mapped[str] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(20))  # text, audio, interactive
    recebida_em: Mapped[datetime] = mapped_column()  # horário do WhatsApp
    processada_em: Mapped[datetime | None] = mapped_column(default=None)
    media_id: Mapped[str | None] = mapped_column(String(200), default=None)
    texto: Mapped[str | None] = mapped_column(Text, default=None)  # texto ou transcrição
    confianca_transcricao: Mapped[float | None] = mapped_column(Float, default=None)
    intencoes: Mapped[dict[str, Any] | None] = mapped_column(default=None)


class StatusPendencia(str, enum.Enum):
    aguardando = "aguardando"
    aguardando_justificativa = "aguardando_justificativa"
    confirmada = "confirmada"
    cancelada = "cancelada"
    expirada = "expirada"


class Pendencia(Base):
    """Grupo de lançamentos de uma mensagem que aguarda o [Confirmar] (RF02)."""

    __tablename__ = "pendencias"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    fazenda_id: Mapped[str] = mapped_column(ForeignKey("fazendas.id"), index=True)
    telefone: Mapped[str] = mapped_column(String(20))
    status: Mapped[StatusPendencia] = mapped_column(Enum(StatusPendencia),
                                                    default=StatusPendencia.aguardando)
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc)
    expira_em: Mapped[datetime] = mapped_column()
    tem_alerta: Mapped[bool] = mapped_column(default=False)
    resolvida_em: Mapped[datetime | None] = mapped_column(default=None)

    lancamentos: Mapped[list["Lancamento"]] = relationship(back_populates="pendencia")


class TipoLancamento(str, enum.Enum):
    manejo = "manejo"
    estorno = "estorno"


class StatusLancamento(str, enum.Enum):
    pendente = "pendente"
    confirmado = "confirmado"
    cancelado = "cancelado"
    expirado = "expirado"


class Lancamento(Base):
    """Registro de manejo com a trilha de auditoria completa (RNF09)."""

    __tablename__ = "lancamentos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    fazenda_id: Mapped[str] = mapped_column(ForeignKey("fazendas.id"), index=True)
    pendencia_id: Mapped[str | None] = mapped_column(ForeignKey("pendencias.id"), default=None)
    mensagem_id: Mapped[str | None] = mapped_column(ForeignKey("mensagens_recebidas.id"), default=None)
    tanque_id: Mapped[str] = mapped_column(ForeignKey("tanques.id"))
    lote_id: Mapped[str | None] = mapped_column(ForeignKey("lotes.id"), default=None)
    tipo: Mapped[TipoLancamento] = mapped_column(Enum(TipoLancamento), default=TipoLancamento.manejo)
    status: Mapped[StatusLancamento] = mapped_column(Enum(StatusLancamento),
                                                     default=StatusLancamento.pendente)
    estorna_id: Mapped[str | None] = mapped_column(ForeignKey("lancamentos.id"), default=None)

    racao_kg: Mapped[float | None] = mapped_column(Float, default=None)
    tipo_racao: Mapped[str | None] = mapped_column(String(100), default=None)
    mortalidade: Mapped[int | None] = mapped_column(Integer, default=None)

    # Três horários (RNF06).
    manejo_em: Mapped[datetime] = mapped_column()
    recebido_em: Mapped[datetime] = mapped_column()
    processado_em: Mapped[datetime] = mapped_column(default=agora_utc)

    # Auditoria (RNF09).
    json_extraido: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    validacao: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    justificativa: Mapped[str | None] = mapped_column(Text, default=None)
    confirmado_por: Mapped[str | None] = mapped_column(String(20), default=None)
    confirmado_em: Mapped[datetime | None] = mapped_column(default=None)

    pendencia: Mapped[Pendencia | None] = relationship(back_populates="lancamentos")
    tanque: Mapped[Tanque] = relationship()
    lote: Mapped[Lote | None] = relationship()


class ConsultaTecnica(Base):
    """Pergunta técnica respondida pelo CAG, com a versão do acervo (RNF10)."""

    __tablename__ = "consultas_tecnicas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    fazenda_id: Mapped[str] = mapped_column(ForeignKey("fazendas.id"), index=True)
    mensagem_id: Mapped[str | None] = mapped_column(ForeignKey("mensagens_recebidas.id"), default=None)
    pergunta: Mapped[str] = mapped_column(Text)
    bloco: Mapped[str | None] = mapped_column(String(100), default=None)
    versao_acervo: Mapped[str | None] = mapped_column(String(100), default=None)
    resposta_enviada: Mapped[str] = mapped_column(Text)
    citacao: Mapped[str | None] = mapped_column(Text, default=None)
    citacao_verificada: Mapped[bool] = mapped_column(default=False)
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc)
