"""Linha de comando: `ipeia <comando>` (ou `python -m ipeia.cli <comando>`).

Comandos:
  criar-banco        cria as tabelas no banco configurado
  demo               cria a fazenda de demonstração (telefone 5584999990000)
  conversar          simulador de WhatsApp no terminal, com os adaptadores configurados
  expirar            expira pendências com mais de 24 h (rodar por cron)
  verificar          confere limites.toml e o tamanho dos blocos do acervo (RNF05)
"""

import argparse
import itertools
import sys

from .banco.sessao import criar_engine, criar_tabelas, fabrica_de_sessoes, transacao
from .cadastro import TELEFONE_DEMO, criar_fazenda_demo
from .cag.acervo import carregar_acervo
from .config import obter_configuracao
from .confirmacao.servico import expirar_pendencias
from .manejo.limites import carregar_limites
from .montagem import montar_orquestrador
from .tempo import agora_utc
from .whatsapp.cliente import ClienteMock
from .whatsapp.mensagens import MensagemEntrada


def _conversar(telefone: str) -> None:
    """Lê mensagens do terminal. '/1', '/2', '/3' tocam os botões da última resposta;
    '/audio <texto>' simula um áudio (o transcritor mock devolve o próprio texto)."""
    cfg = obter_configuracao()
    whatsapp = ClienteMock()
    orq = montar_orquestrador(cfg, whatsapp=whatsapp)
    contador = itertools.count(1)
    ultimos_botoes = []
    print("Simulador IPEIA. Digite mensagens; /1 /2 /3 tocam botões; /audio <texto>; Ctrl+D sai.")
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        n = next(contador)
        base = dict(wa_message_id=f"sim-{agora_utc().timestamp()}-{n}", telefone=telefone,
                    recebida_em=agora_utc())
        if linha in {"/1", "/2", "/3"} and len(ultimos_botoes) >= int(linha[1]):
            b = ultimos_botoes[int(linha[1]) - 1]
            entrada = MensagemEntrada(tipo="interactive", botao_id=b.id, texto=b.titulo, **base)
        elif linha.startswith("/audio "):
            media = f"midia-{n}"
            whatsapp.midias[media] = linha.removeprefix("/audio ").encode()
            entrada = MensagemEntrada(tipo="audio", media_id=media, mime="audio/ogg", **base)
        else:
            entrada = MensagemEntrada(tipo="text", texto=linha, **base)
        inicio = len(whatsapp.enviadas)
        orq.processar(entrada)
        for enviada in whatsapp.enviadas[inicio:]:
            print("\n🤖 " + enviada.texto)
            if enviada.botoes:
                print("   " + "  ".join(f"[/{i}] {b.titulo}" for i, b in enumerate(enviada.botoes, 1)))
                ultimos_botoes = enviada.botoes
        print()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ipeia")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("criar-banco")
    sub.add_parser("demo")
    conversa = sub.add_parser("conversar")
    conversa.add_argument("--telefone", default=TELEFONE_DEMO)
    sub.add_parser("expirar")
    sub.add_parser("verificar")
    args = parser.parse_args(argv)

    cfg = obter_configuracao()
    if args.comando == "criar-banco":
        criar_tabelas(criar_engine(cfg.database_url))
        print("Tabelas criadas.")
    elif args.comando == "demo":
        engine = criar_engine(cfg.database_url)
        criar_tabelas(engine)
        with transacao(fabrica_de_sessoes(engine)) as sessao:
            fazenda = criar_fazenda_demo(sessao)
        print(f"Fazenda demo criada ({fazenda.id}). Telefone: {TELEFONE_DEMO}")
    elif args.comando == "conversar":
        _conversar(args.telefone)
    elif args.comando == "expirar":
        with transacao(fabrica_de_sessoes(criar_engine(cfg.database_url))) as sessao:
            print(f"{expirar_pendencias(sessao)} pendência(s) expirada(s).")
    elif args.comando == "verificar":
        limites = carregar_limites(cfg.limites_path)
        print(f"Limites {limites.versao} (responsável: {limites.responsavel}): "
              f"{', '.join(limites.especies)}")
        acervo = carregar_acervo(cfg.acervo_dir)
        for b in acervo.blocos.values():
            print(f"Bloco {b.versao_completa}: {len(b.manuais)} manual(is), ~{b.tokens_estimados()} tokens")
        excedentes = acervo.verificar_tamanho(cfg.cag_janela_tokens)
        for e in excedentes:
            print("ATENÇÃO, bloco grande demais:", e)
        sys.exit(1 if excedentes else 0)


if __name__ == "__main__":
    main()
