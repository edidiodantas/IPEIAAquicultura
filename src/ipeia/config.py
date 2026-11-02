"""Configuração lida de variáveis de ambiente (prefixo IPEIA_) ou do arquivo .env.

A escolha de hardware e hospedagem fica toda aqui: trocar o motor de linguagem,
a transcrição ou o WhatsApp é só mudar o *_BACKEND, sem tocar no código.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IPEIA_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./ipeia.db"
    fuso_horario: str = "America/Sao_Paulo"

    # Motor de linguagem (RNF01). "openai" cobre vLLM local, Modal, Hetzner e APIs por token.
    llm_backend: Literal["mock", "openai"] = "mock"
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = ""
    llm_modelo: str = "amadeusai/Amadeus-Verbo-MI-Qwen2.5-7B-PT-BR-Instruct"
    llm_timeout_s: float = 180.0
    llm_semente: int = 42

    # Transcrição (RF01).
    stt_backend: Literal["mock", "faster_whisper", "openai"] = "mock"
    stt_base_url: str = "http://localhost:8001/v1"
    stt_api_key: str = ""
    stt_modelo: str = "large-v3-turbo"
    stt_confianca_minima: float = 0.6

    # WhatsApp (RF02).
    whatsapp_backend: Literal["mock", "cloud"] = "mock"
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = "troque-este-token"
    whatsapp_api_versao: str = "v21.0"

    # Regras de negócio e acervo.
    limites_path: Path = RAIZ_PROJETO / "config" / "limites.toml"
    acervo_dir: Path = RAIZ_PROJETO / "acervo"
    # RNF05: cada bloco do acervo deve caber em até metade da janela efetiva do modelo.
    cag_janela_tokens: int = 32768


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()
