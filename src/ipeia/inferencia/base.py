"""Interfaces do motor de linguagem e da transcrição."""

from dataclasses import dataclass
from typing import Any, Protocol


class ModeloLinguagem(Protocol):
    """Motor de linguagem (Amadeus-Verbo em produção).

    Toda chamada é determinística: temperatura 0.0 e semente fixa (RNF02).
    `gerar_json` deve usar decodificação guiada pelo esquema quando o servidor
    oferecer (vLLM oferece), para que o modelo não consiga sair do esquema.
    """

    def gerar_json(self, sistema: str, usuario: str, esquema: dict[str, Any]) -> dict[str, Any]:
        """Devolve um objeto que obedece ao esquema JSON informado."""
        ...


@dataclass(frozen=True)
class Transcricao:
    texto: str
    confianca: float  # de 0 a 1


class Transcritor(Protocol):
    """Transcrição de áudio (Whisper em produção)."""

    def transcrever(self, audio: bytes, mime: str = "audio/ogg") -> Transcricao: ...


# Vocabulário passado como prompt inicial ao Whisper (RF01).
VOCABULARIO_AQUICOLA = (
    "Manejo de piscicultura: tanque, viveiro, alevino, juvenil, engorda, arraçoamento, "
    "ração extrusada, saco de ração, biometria, despesca, tilápia, tambaqui, tambacu, "
    "pirarucu, camarão, oxigênio dissolvido, aerador, mortalidade, lote."
)
