# IPEIAAquicultura

Assistente de gestão aquícola via WhatsApp. O produtor manda um áudio com o manejo do dia ou com uma dúvida técnica. O sistema transcreve o áudio, extrai os dados com o modelo brasileiro Amadeus-Verbo, valida os limites zootécnicos por código e pede confirmação antes de gravar. As dúvidas técnicas são respondidas somente a partir de manuais homologados, como os da Embrapa.

## Documentos

- [Especificação revisada (v2)](docs/especificacao-v2.md): requisitos funcionais e não funcionais, correções em relação à v1 e decisões em aberto.
- [Arquitetura e custo estimado](docs/arquitetura.md): fluxo do áudio até o banco, componentes, dimensionamento da GPU e custo mensal.
- [Piloto no servidor próprio (RTX 3050 6 GB)](docs/servidor-proprio.md): qual Amadeus-Verbo cabe, llama.cpp, latência e instalação.
- [Relatórios para impressão](relatorios/00-LEIA-ME.txt): panorama em texto simples do que foi feito, em ordem cronológica.
- [Guia de desenvolvimento](docs/desenvolvimento.md): como rodar localmente, trocar o motor de inferência e o mapa dos módulos.

## Começo rápido

```bash
pip install -e ".[dev]"
ipeia demo        # fazenda de demonstração em SQLite
ipeia conversar   # simulador de WhatsApp no terminal, sem GPU
pytest -q
```

## Plano

1. Revisar a especificação (concluído).
2. Desenhar a arquitetura e estimar o custo (concluído, aguardando as decisões em aberto).
3. Codificar o núcleo do MVP com inferência trocável (em andamento).
4. Planejar o piloto: critérios de aceite e testes com áudios reais.
