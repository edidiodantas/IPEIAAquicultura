"""Dicionário dinâmico de apelidos de tanques (RF04)."""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..banco.modelos import ApelidoTanque, Tanque

_PREFIXOS = re.compile(r"^(?:n?[oa]s?\s+)?(?:tanque|viveiro)?\s*", re.IGNORECASE)
LIMIAR_SIMILARIDADE = 0.82
MARGEM_EMPATE = 0.05


def normalizar(texto: str) -> str:
    """'No Tanque da Entrada' -> 'da entrada'; 'T-3' -> 't3'."""
    s = "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s.lower()).strip(" .,;:!?")
    s = _PREFIXOS.sub("", s).strip()
    return re.sub(r"(?<=[a-z])[-\s](?=\d)", "", s)


@dataclass
class ResultadoApelido:
    status: Literal["ok", "ambiguo", "desconhecido"]
    tanque: Tanque | None = None
    candidatos: list[Tanque] = field(default_factory=list)


def _numero(texto: str) -> str | None:
    m = re.fullmatch(r"[a-z]*0*(\d+)", texto)
    return m.group(1) if m else None


def resolver_tanque(sessao: Session, fazenda_id: str, dito: str) -> ResultadoApelido:
    alvo = normalizar(dito)
    tanques = list(sessao.scalars(select(Tanque).where(Tanque.fazenda_id == fazenda_id)))
    apelidos = list(sessao.scalars(select(ApelidoTanque).where(ApelidoTanque.fazenda_id == fazenda_id)))
    if not alvo or not tanques:
        return ResultadoApelido("desconhecido")

    nomes: list[tuple[str, Tanque]] = [(normalizar(t.codigo), t) for t in tanques]
    nomes += [(a.apelido, a.tanque) for a in apelidos]

    exatos = {t.id: t for nome, t in nomes if nome == alvo}
    if len(exatos) == 1:
        return ResultadoApelido("ok", next(iter(exatos.values())))

    # "tanque 3" casa com o código "T3" ou "03".
    numero = _numero(alvo)
    if numero:
        por_numero = {t.id: t for nome, t in nomes if _numero(nome) == numero}
        if len(por_numero) == 1:
            return ResultadoApelido("ok", next(iter(por_numero.values())))
        if len(por_numero) > 1:
            return ResultadoApelido("ambiguo", candidatos=list(por_numero.values()))
        return ResultadoApelido("desconhecido")

    pontuados: dict[str, tuple[float, Tanque]] = {}
    for nome, tanque in nomes:
        nota = SequenceMatcher(None, alvo, nome).ratio()
        if nota >= LIMIAR_SIMILARIDADE and nota > pontuados.get(tanque.id, (0.0, tanque))[0]:
            pontuados[tanque.id] = (nota, tanque)
    if not pontuados:
        return ResultadoApelido("desconhecido")
    ordenados = sorted(pontuados.values(), key=lambda x: x[0], reverse=True)
    if len(ordenados) > 1 and ordenados[0][0] - ordenados[1][0] < MARGEM_EMPATE:
        return ResultadoApelido("ambiguo", candidatos=[t for _, t in ordenados])
    return ResultadoApelido("ok", ordenados[0][1])


_RE_CADASTRO = re.compile(r"^\s*apelido\s*:?\s*(.+?)\s*=\s*(.+?)\s*$", re.IGNORECASE)


def interpretar_cadastro(texto: str) -> tuple[str, str] | None:
    """Comando do WhatsApp para cadastrar apelido: 'apelido tanque do fundo = T3'."""
    m = _RE_CADASTRO.match(texto)
    return (m.group(1), m.group(2)) if m else None


def cadastrar_apelido(sessao: Session, fazenda_id: str, apelido: str, codigo: str) -> Tanque | None:
    tanque = sessao.scalar(select(Tanque).where(Tanque.fazenda_id == fazenda_id,
                                                Tanque.codigo.ilike(codigo.strip())))
    if tanque is None:
        return None
    nome = normalizar(apelido)
    existente = sessao.scalar(select(ApelidoTanque).where(ApelidoTanque.fazenda_id == fazenda_id,
                                                          ApelidoTanque.apelido == nome))
    if existente:
        existente.tanque_id = tanque.id
    else:
        sessao.add(ApelidoTanque(fazenda_id=fazenda_id, tanque_id=tanque.id, apelido=nome))
    return tanque
