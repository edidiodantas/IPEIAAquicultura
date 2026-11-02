"""Fila de processamento assíncrono (RNF06).

O webhook só grava na fila e responde 200 à Meta na hora. Hoje a fila roda no
próprio processo (thread em segundo plano). Para produção serverless, troque por
uma implementação com SQS, Cloud Tasks ou a fila do Modal com a mesma interface.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from .whatsapp.mensagens import MensagemEntrada

log = logging.getLogger(__name__)


class Fila(Protocol):
    def enfileirar(self, mensagem: MensagemEntrada) -> None: ...


class FilaImediata:
    """Processa na hora, no mesmo fluxo. Útil em testes e no simulador."""

    def __init__(self, processar: Callable[[MensagemEntrada], None]):
        self._processar = processar

    def enfileirar(self, mensagem: MensagemEntrada) -> None:
        self._processar(mensagem)


class FilaEmThreads:
    """Processa em segundo plano, com um número fixo de threads."""

    def __init__(self, processar: Callable[[MensagemEntrada], None], trabalhadores: int = 4):
        self._processar = processar
        self._executor = ThreadPoolExecutor(max_workers=trabalhadores, thread_name_prefix="ipeia")

    def enfileirar(self, mensagem: MensagemEntrada) -> None:
        self._executor.submit(self._seguro, mensagem)

    def _seguro(self, mensagem: MensagemEntrada) -> None:
        try:
            self._processar(mensagem)
        except Exception:  # noqa: BLE001 - registra e segue; a mensagem não foi gravada
            log.exception("falha ao processar %s", mensagem.wa_message_id)
