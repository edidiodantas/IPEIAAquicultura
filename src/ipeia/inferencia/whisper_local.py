"""faster-whisper rodando na mesma máquina (GPU local, Hetzner ou contêiner do Modal).

Instale com `pip install -e .[whisper-local]`. O modelo só é carregado no primeiro uso.
"""

import io
import math

from .base import VOCABULARIO_AQUICOLA, Transcricao


class TranscritorFasterWhisper:
    def __init__(self, modelo: str = "large-v3-turbo", dispositivo: str = "auto",
                 tipo_computacao: str = "default"):
        self._nome_modelo = modelo
        self._dispositivo = dispositivo
        self._tipo_computacao = tipo_computacao
        self._modelo = None

    def _carregar(self):
        if self._modelo is None:
            from faster_whisper import WhisperModel  # importação tardia: dependência opcional

            self._modelo = WhisperModel(self._nome_modelo, device=self._dispositivo,
                                        compute_type=self._tipo_computacao)
        return self._modelo

    def transcrever(self, audio: bytes, mime: str = "audio/ogg") -> Transcricao:
        segmentos, _ = self._carregar().transcribe(
            io.BytesIO(audio), language="pt", initial_prompt=VOCABULARIO_AQUICOLA,
            vad_filter=True, temperature=0.0,
        )
        segmentos = list(segmentos)
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        if not segmentos:
            return Transcricao(texto="", confianca=0.0)
        media = sum(s.avg_logprob for s in segmentos) / len(segmentos)
        return Transcricao(texto=texto, confianca=max(0.0, min(1.0, math.exp(media))))
