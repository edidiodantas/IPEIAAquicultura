"""Adaptadores de inferência trocáveis (RNF01, RNF04).

O resto do sistema só conhece as interfaces de `base.py`. A implementação
concreta (mock, vLLM local, Modal, Hetzner, API por token, faster-whisper)
é escolhida pela configuração em `fabrica.py`.
"""

from .base import ModeloLinguagem, Transcricao, Transcritor
from .fabrica import criar_modelo_linguagem, criar_transcritor

__all__ = [
    "ModeloLinguagem",
    "Transcricao",
    "Transcritor",
    "criar_modelo_linguagem",
    "criar_transcritor",
]
