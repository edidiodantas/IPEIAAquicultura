#!/usr/bin/env bash
# Baixa um Amadeus-Verbo do Hugging Face, converte para GGUF e quantiza.
# Não há GGUF oficial publicado pela Amadeus AI, por isso a conversão é local.
#
# Uso:  deploy/preparar_modelo.sh 3B Q6_K      (perfil A, recomendado)
#       deploy/preparar_modelo.sh 7B Q4_K_M    (perfil B, comparação)
#
# Requer: llama.cpp compilado com CUDA em $LLAMA_CPP (padrão /opt/llama.cpp) e
#         pip install -U "huggingface_hub[cli]" -r $LLAMA_CPP/requirements.txt
set -euo pipefail

TAMANHO="${1:-3B}"
QUANT="${2:-Q6_K}"
LLAMA_CPP="${LLAMA_CPP:-/opt/llama.cpp}"
DESTINO="${DESTINO:-/srv/ipeia/modelos}"
REPO="amadeusai/Amadeus-Verbo-MI-Qwen-2.5-${TAMANHO}-PT-BR-Instruct-Experimental"
NOME="amadeus-verbo-mi-${TAMANHO,,}"

mkdir -p "$DESTINO/hf"
echo ">> Baixando $REPO"
huggingface-cli download "$REPO" --local-dir "$DESTINO/hf/$NOME"

echo ">> Convertendo para GGUF (F16)"
python3 "$LLAMA_CPP/convert_hf_to_gguf.py" "$DESTINO/hf/$NOME" \
  --outtype f16 --outfile "$DESTINO/$NOME-f16.gguf"

echo ">> Quantizando para $QUANT"
"$LLAMA_CPP/build/bin/llama-quantize" "$DESTINO/$NOME-f16.gguf" \
  "$DESTINO/$NOME-$QUANT.gguf" "$QUANT"

rm -f "$DESTINO/$NOME-f16.gguf"
echo ">> Pronto: $DESTINO/$NOME-$QUANT.gguf"
echo "   Os pesos originais ficam em $DESTINO/hf/$NOME (apague se faltar disco)."
