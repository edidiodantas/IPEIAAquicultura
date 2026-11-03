"""Escolhe a implementação de cada interface a partir da configuração."""

from ..config import Configuracao
from .base import ModeloLinguagem, Transcritor


def criar_modelo_linguagem(cfg: Configuracao) -> ModeloLinguagem:
    if cfg.llm_backend == "mock":
        from .mock import ModeloMock

        return ModeloMock()
    from .openai_compat import ModeloOpenAICompat

    return ModeloOpenAICompat(cfg.llm_base_url, cfg.llm_modelo, cfg.llm_api_key,
                              cfg.llm_timeout_s, cfg.llm_semente)


def criar_transcritor(cfg: Configuracao) -> Transcritor:
    if cfg.stt_backend == "mock":
        from .mock import TranscritorMock

        return TranscritorMock()
    if cfg.stt_backend == "faster_whisper":
        from .whisper_local import TranscritorFasterWhisper

        return TranscritorFasterWhisper(cfg.stt_modelo, cfg.stt_dispositivo,
                                        cfg.stt_tipo_computacao)
    from .openai_compat import TranscritorOpenAICompat

    return TranscritorOpenAICompat(cfg.stt_base_url, cfg.stt_modelo, cfg.stt_api_key)
