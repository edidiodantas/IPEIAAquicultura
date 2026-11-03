# Piloto no servidor próprio (RTX 3050 6 GB)

3 de novembro de 2026 · Edídio

Servidor em São Paulo: RTX 3050 com 6 GB de VRAM, 16 GB de RAM, NVMe de 250 GB, Ubuntu Server. Um engenheiro de pesca no Ceará testa pelo WhatsApp.

**Recomendação:** começar o piloto com o **Amadeus-Verbo MI 3B em GGUF Q6_K**, servido pelo **llama-server (llama.cpp)**, com o **Whisper large-v3-turbo na mesma GPU**. Nessa configuração tudo cabe com folga e o acervo do CAG pode usar blocos de até 16 mil tokens. Em paralelo, rodar os mesmos áudios do piloto no **7B Q4_K_M** (perfil B) e decidir pelo resultado medido, não pelo tamanho do modelo. A troca é só de variáveis de ambiente.

Os números de memória e velocidade abaixo são estimativas a partir da arquitetura do Qwen2.5 e do tamanho típico dos arquivos GGUF. Precisam ser medidos no servidor com `nvidia-smi` e com o `llama-bench`.

## 1. O que existe da família Amadeus-Verbo

A família é baseada no Qwen2.5 e sai em 0,5B, 1,5B, **3B**, **7B**, 14B, 32B e 72B ([coleção no Hugging Face](https://huggingface.co/collections/amadeusai/amadeus-verbo-qwen25-pt-br-powered-by-aws)). Não existe versão de 3,5B. O "3B" tem 3,1 bilhões de parâmetros e janela de 32 mil tokens ([ficha do modelo](https://featherless.ai/models/amadeusai/Amadeus-Verbo-MI-Qwen-2.5-3B-PT-BR-Instruct-Experimental)).

- O nome exato do 7B MI é `amadeusai/Amadeus-Verbo-MI-Qwen-2.5-7B-PT-BR-Instruct-Experimental`. A configuração do projeto usava um nome que não existe e foi corrigida.
- As variantes MI e BI estão marcadas como **Experimental**. A variante FI (`Amadeus-Verbo-FI-Qwen2.5-7B-PT-BR-Instruct`) não tem essa marca e vale entrar na comparação.
- A Amadeus AI não publica GGUF. A conversão é feita localmente com o [`deploy/preparar_modelo.sh`](../deploy/preparar_modelo.sh), que leva poucos minutos.

## 2. Quanto cabe em 6 GB

Num Ubuntu Server sem interface gráfica sobram cerca de 5,7 GB úteis. A conta de cada perfil:

| Item | Perfil A: 3B Q6_K + Whisper na GPU | Perfil B: 7B Q4_K_M, Whisper na CPU |
| --- | --- | --- |
| Pesos do modelo | ~2,5 GB | ~4,7 GB |
| Janela (contexto) | 32.768 tokens | 8.192 tokens |
| KV-Cache em q8_0 | ~0,6 GB (36 KB/token em f16) | ~0,25 GB (56 KB/token em f16) |
| Buffers de cálculo e CUDA | ~0,7 GB | ~0,7 GB |
| Whisper large-v3-turbo int8 | ~1,0 GB na GPU | 0 (vai para a RAM, ~2 GB) |
| **Total na GPU** | **~4,8 GB** | **~5,6 GB, no limite** |
| Maior bloco do acervo (metade da janela) | ~16 mil tokens | ~4 mil tokens |

O ponto que mais pesa é o último. No perfil B, cada bloco do CAG fica com cerca de 4 mil tokens, umas 6 a 8 páginas de manual. Um livro da Embrapa vira muitos blocos pequenos e o roteador precisa acertar o bloco certo. No perfil A, um capítulo inteiro cabe num bloco.

O 7B com 16 mil tokens de janela não cabe junto com o Whisper. Dá para tentar o 7B em IQ4_XS (~4,2 GB) com 12 mil tokens, mas fica no limite de novo.

A RAM de 16 GB comporta o PostgreSQL, a API, o Whisper na CPU (perfil B) e 4 GB de cache de prompts do llama-server (`--cache-ram 4096`). O disco de 250 GB comporta os pesos originais dos dois modelos (~22 GB) e os GGUF.

## 3. Por que llama.cpp e não vLLM nem Ollama

- **vLLM** foi pensado para GPU grande. Ele reserva a memória toda de uma vez, e o 7B em AWQ mais o KV-Cache não cabe em 6 GB com folga. Continua sendo a escolha para a nuvem (docs/arquitetura.md).
- **Ollama** funciona, mas usa uma janela padrão pequena e corta o texto sem avisar quando o prompt passa dela. No CAG isso apaga parte do manual em silêncio. Se o servidor já tem Ollama, dá para usar fixando a janela (seção 7).
- **llama-server** fala a mesma API da OpenAI que o projeto já usa. Ele aceita `response_format` com `json_schema` (conferido no código do servidor), então a decodificação guiada do RF03 funciona sem mudar nada no adaptador. Ele também guarda o KV-Cache de prompts anteriores na RAM (`--cache-ram`) e reaproveita o prefixo igual (o bloco do acervo), o que atende o RNF05 com um único slot.

## 4. Latência esperada para um áudio de 20 segundos

| Etapa | Perfil A | Perfil B |
| --- | --- | --- |
| Transcrição (Whisper turbo) | 1 a 3 s na GPU | 5 a 15 s na CPU, conforme o processador |
| Roteador de intenção | < 1 s | ~1 s |
| Extração JSON (~100 tokens de saída) | 2 a 3 s | 4 a 6 s |
| Resposta do CAG com o bloco já em cache | 3 a 5 s | 6 a 10 s |
| Primeira pergunta de um bloco (sem cache) | +8 s para 16 mil tokens | +8 s para 4 mil tokens |

Para um único usuário, as duas opções ficam bem abaixo do limite de 3 minutos do RNF08. A distância São Paulo–Ceará não pesa: a mensagem passa pelos servidores da Meta e acrescenta menos de 1 segundo.

## 5. Por que o 3B é aceitável aqui

O projeto não confia no modelo para proteger os dados. Os três bloqueios são código:

1. A decodificação guiada impede JSON fora do esquema.
2. O Pydantic barra ração e mortalidade fora dos limites (RF05), e o produtor confirma tudo pelo botão (RF02).
3. No CAG, o código confere se a citação existe no manual. Se não existir, sai a frase padrão (RNF03).

Um modelo menor erra mais, mas o erro aparece como "não entendi" ou "não encontrei", não como dado errado no banco. O que precisa ser medido é a taxa desses erros nos áudios reais do engenheiro.

## 6. Como medir e decidir

1. Guardar todos os áudios e textos do piloto (já ficam na trilha de auditoria).
2. Depois de umas 50 mensagens, reprocessar as mesmas mensagens com o perfil B.
3. Comparar: extrações corretas na primeira tentativa, respostas do CAG com citação válida e tempo até os botões.
4. Ficar com o 3B se a diferença for pequena. Passar para o 7B (ou para a nuvem) se o 3B errar muito na extração.

## 7. Instalação no servidor

O servidor já tem Python e um "llama" instalados, e a RTX 3050 de 6 GB é o modelo novo (2024), que foi a base das estimativas acima. Primeiro, confira qual "llama" está instalado:

```bash
nvidia-smi                    # a placa e o driver aparecem?
which llama-server ollama     # llama.cpp, Ollama ou os dois?
python3 --version             # o projeto pede 3.11 ou mais novo
```

### Se for o llama.cpp (`llama-server`)

Não precisa compilar de novo. Confira se ele foi compilado com CUDA (`llama-server --list-devices` deve mostrar a RTX 3050) e ajuste o caminho na unidade systemd e no script, se não estiver em `/opt/llama.cpp`.

```bash
export LLAMA_CPP=/caminho/do/llama.cpp     # onde estão convert_hf_to_gguf.py e build/bin
pip install -U "huggingface_hub[cli]" -r $LLAMA_CPP/requirements.txt
deploy/preparar_modelo.sh 3B Q6_K       # perfil A
deploy/preparar_modelo.sh 7B Q4_K_M     # perfil B, para a comparação

sudo cp deploy/llama-server.service /etc/systemd/system/   # corrija o caminho do llama-server
sudo systemctl daemon-reload && sudo systemctl enable --now llama-server
```

### Se for o Ollama

O Ollama também serve, com dois cuidados:

1. **Fixar a janela.** O Ollama usa uma janela padrão pequena e corta o começo do prompt sem avisar. Defina a janela no Modelfile e use o mesmo valor em `IPEIA_CAG_JANELA_TOKENS`.
2. **Importar o GGUF.** Não há Amadeus-Verbo na biblioteca do Ollama. Gere o GGUF com o `preparar_modelo.sh` (ele precisa só do código-fonte do llama.cpp, sem compilar a parte de GPU) e importe:

```bash
cat > Modelfile <<'MF'
FROM /srv/ipeia/modelos/amadeus-verbo-mi-3b-Q6_K.gguf
PARAMETER num_ctx 32768
PARAMETER temperature 0
MF
ollama create amadeus-verbo-3b -f Modelfile
```

No `.env`, use `IPEIA_LLM_BASE_URL=http://127.0.0.1:11434/v1` e `IPEIA_LLM_MODELO=amadeus-verbo-3b`. O Ollama aceita o `response_format` com `json_schema` no endpoint compatível com a OpenAI. A diferença em relação ao llama-server é o cache: o Ollama guarda só o último prompt, então alternar entre manejo e consulta técnica faz o bloco do acervo ser reprocessado (cerca de 8 s a mais). Para um único usuário isso é aceitável.

### O projeto

```bash
pip install -e ".[postgres,whisper-local]"
cp .env.example .env   # e ativar o bloco "Perfil A" no fim do arquivo
uvicorn ipeia.api.app:app --host 127.0.0.1 --port 8080
```

## 8. WhatsApp e acesso externo

- A Meta precisa alcançar o webhook por HTTPS. Num servidor atrás de roteador, o caminho mais simples é um túnel (por exemplo, Cloudflare Tunnel) apontando para `127.0.0.1:8080`, sem abrir porta no roteador.
- No modo de teste da WhatsApp Cloud API, o número do engenheiro precisa estar na lista de destinatários autorizados do app. O QR code pode ser o link `wa.me` do número do projeto.
- Não usar bibliotecas que conectam por QR code do WhatsApp Web (não oficiais). Elas não têm os botões nativos do RF02 e o número pode ser bloqueado.

## 9. O que muda em relação à especificação

O servidor próprio não é serverless (RNF04). Para um piloto com uma pessoa, isso reduz o custo a energia elétrica. Os dados ficam no Brasil, o que simplifica a LGPD (RNF07). Quando o número de fazendas crescer, o mesmo código vai para a nuvem trocando só o `IPEIA_LLM_BASE_URL`.
