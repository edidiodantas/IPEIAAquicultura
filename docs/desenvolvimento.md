# Guia de desenvolvimento

2 de novembro de 2026

O código do MVP fica em `src/ipeia/`, dividido em módulos pequenos. A inferência
(Amadeus-Verbo e Whisper) e o WhatsApp ficam atrás de interfaces, para que a
escolha de hardware e hospedagem possa ser feita depois sem mexer no resto.

## Rodar localmente, sem GPU

```bash
pip install -e ".[dev]"
cp .env.example .env          # os padrões já usam SQLite e os adaptadores mock
ipeia demo                    # cria a fazenda de demonstração
ipeia conversar               # simulador de WhatsApp no terminal
pytest -q                     # testes
```

No simulador, `/1`, `/2` e `/3` tocam os botões da última resposta, e
`/audio <texto>` simula um áudio. Exemplos para testar:

- `Dei 8 kg de ração no tanque da entrada e meio saco no tanque do meio, morreram 3 no tanque do meio.`
- `100 kg no tanque 3` (bloqueio: 200% da biomassa)
- `12 kg no tanque 1` (alerta: pede justificativa ao confirmar)
- `Qual o oxigênio mínimo para tilápia?` (resposta com citação e aviso)
- `O de hoje no tanque 2 foi 20 kg, não 12,5.` (correção com estorno)
- `apelido tanque grande = T2` (cadastra apelido)

A API sobe com `uvicorn ipeia.api.app:app --reload`. O webhook fica em
`/webhook/whatsapp` (GET para a verificação da Meta, POST para as mensagens).

## Trocar o motor de inferência

Tudo é configurado por variáveis `IPEIA_*` (ver `.env.example`).

| Onde roda | Configuração |
| --- | --- |
| Sem GPU (desenvolvimento e testes) | `IPEIA_LLM_BACKEND=mock`, `IPEIA_STT_BACKEND=mock` |
| vLLM na própria máquina ou no Hetzner | `IPEIA_LLM_BACKEND=openai`, `IPEIA_LLM_BASE_URL=http://<servidor>:8000/v1` e `IPEIA_STT_BACKEND=faster_whisper` |
| vLLM e Whisper no Modal | `IPEIA_LLM_BACKEND=openai`, `IPEIA_LLM_BASE_URL=https://<app>.modal.run/v1`, `IPEIA_STT_BACKEND=openai` |
| API por token | `IPEIA_LLM_BACKEND=openai`, URL e `IPEIA_LLM_API_KEY` do provedor |

O adaptador `openai` usa o formato da API da OpenAI, que o vLLM serve com
`vllm serve <modelo> --enable-prefix-caching`. Toda chamada vai com
temperatura 0, semente fixa e o esquema JSON da tarefa (decodificação guiada).

Para um provedor que não siga esse formato, crie uma classe com o método
`gerar_json` (ver `inferencia/base.py`) e registre-a em `inferencia/fabrica.py`.

## Mapa dos módulos

| Módulo | Responsabilidade | Requisitos |
| --- | --- | --- |
| `config.py` | Configuração por variáveis de ambiente | |
| `tempo.py` | Horários do manejo, do recebimento e do processamento | RNF06 |
| `inferencia/` | Interfaces e adaptadores do LLM e da transcrição (mock, HTTP, faster-whisper) | RF01, RNF01, RNF02 |
| `whatsapp/` | Webhook (parse e assinatura) e cliente de envio (mock e Cloud API) | RF01, RF02 |
| `roteamento/` | Classifica e divide a mensagem em manejo, consulta, correção ou outro | RF08 |
| `manejo/esquemas.py` | Esquema JSON da extração e da correção | RF03, RF10 |
| `manejo/extracao.py` | Prompts e chamada ao modelo | RF03 |
| `manejo/apelidos.py` | Resolve apelidos de tanques e cadastra novos | RF04 |
| `manejo/limites.py` | Lê `config/limites.toml` | RF05 |
| `manejo/validacao.py` | Regras zootécnicas em Pydantic (alerta e bloqueio) | RF05 |
| `manejo/servico.py` | Fluxo de manejo até a pendência | RF02 a RF05 |
| `manejo/correcao.py` | Estorno e correção de lançamentos confirmados | RF10 |
| `confirmacao/` | Botões Confirmar, Corrigir e Cancelar, justificativa e expiração | RF02 |
| `cag/` | Acervo em blocos, escolha do bloco, barreira de citação e aviso | RF06, RF07, RNF03, RNF05, RNF10 |
| `cag/ingestao.py`, `cag/temas.py` | Extração de livros em PDF e sugestão de blocos por tema (`ipeia ingerir`, ver `acervo/README.md`) | RF06, RNF05, RNF10 |
| `banco/` | Modelos SQLAlchemy e sessão com RLS | RNF07, RNF09 |
| `orquestrador.py` | Recebe a mensagem e chama o fluxo certo | |
| `api/app.py` | FastAPI: webhook e `/saude` | |
| `fila.py` | Fila assíncrona (hoje em threads; trocar por SQS, Cloud Tasks ou Modal) | RNF06 |
| `cadastro.py` | Funções de cadastro da fazenda e a fazenda demo | RF09 |
| `cli.py` | Comandos `ipeia ...` | |

## PostgreSQL e isolamento por fazenda

```bash
docker compose up -d
export IPEIA_DATABASE_URL=postgresql+psycopg://ipeia:ipeia@localhost:5432/ipeia
pip install -e ".[postgres]"
ipeia criar-banco
psql "postgresql://ipeia:ipeia@localhost:5432/ipeia" -f sql/rls_postgres.sql
```

A aplicação deve conectar com um papel que não seja dono das tabelas (por exemplo,
`ipeia_app`), para que o RLS valha. O teste `tests/test_postgres_rls.py` confere o
isolamento quando as variáveis `IPEIA_TEST_PG_DONO` e `IPEIA_TEST_PG_APP` estão
definidas, como no CI.

## Decisões em aberto tratadas como configuração

| Decisão da v2 | Onde está | Valor padrão |
| --- | --- | --- |
| Espécies do MVP | `config/limites.toml` | Tilápia e tambaqui |
| Limites zootécnicos e quem assina | `config/limites.toml` (`responsavel`, `versao`) | Valores provisórios, marcados como "A DEFINIR" |
| Manuais do acervo | `acervo/` | Dois blocos fictícios `exemplo-*`, só para testes |
| Peso do saco de ração | Cadastro da fazenda | 25 kg |
| Hospedagem da inferência | `.env` | Mock |

## O que ainda falta

- Guardar o áudio em armazenamento de objetos com expiração de 90 dias (RNF07, RNF09). Hoje só o ID da mídia e a transcrição são gravados.
- Fila gerenciada para produção serverless (RNF04, RNF06).
- Painel web de cadastro (RF09). Hoje o cadastro é feito por código (`cadastro.py`) e os apelidos também pelo WhatsApp.
- Migrações de banco (Alembic) quando o esquema estabilizar.
- Conjunto de regressão com áudios reais (RNF01, RNF11). O `ModeloMock` não mede acurácia.
- Consulta ao histórico pelo WhatsApp, se for aprovada como RF11.
