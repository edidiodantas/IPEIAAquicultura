"""Monta o sistema a partir da configuração (injeção de dependências em um lugar só)."""

from .banco.sessao import criar_engine, criar_tabelas, fabrica_de_sessoes
from .cag.acervo import carregar_acervo
from .config import Configuracao
from .inferencia import criar_modelo_linguagem, criar_transcritor
from .manejo.limites import carregar_limites
from .orquestrador import Orquestrador
from .whatsapp.cliente import ClienteWhatsApp, criar_cliente


def montar_orquestrador(cfg: Configuracao, whatsapp: ClienteWhatsApp | None = None,
                        criar_banco: bool = True) -> Orquestrador:
    engine = criar_engine(cfg.database_url)
    if criar_banco:
        criar_tabelas(engine)
    return Orquestrador(
        fabrica_sessoes=fabrica_de_sessoes(engine),
        cfg=cfg,
        modelo=criar_modelo_linguagem(cfg),
        transcritor=criar_transcritor(cfg),
        whatsapp=whatsapp or criar_cliente(cfg),
        limites=carregar_limites(cfg.limites_path),
        acervo=carregar_acervo(cfg.acervo_dir),
    )
