# Acervo técnico (CAG)

Cada pasta é um **bloco temático** (RF06, RNF05). Só o bloco escolhido pelo
roteador entra no prompt, e o vLLM mantém esse prefixo em KV-Cache.

```
acervo/<bloco>/bloco.toml        descrição, versão e lista de manuais do bloco
acervo/<bloco>/<manual>.md       texto do manual, com <!-- pagina: N --> antes de cada página
acervo/_livros/<livro>/livro.md  texto de um livro em PDF, gerado por `ipeia ingerir`
acervo/_livros/<livro>/livro.toml metadados, licença e capítulos com tokens e temas sugeridos
```

Regras:

- Cada bloco deve caber em até metade da janela de contexto do modelo. Confira com `ipeia verificar`.
- Todo manual precisa de `versao`, `homologado_em` e `licenca` (RNF10). `ipeia verificar` falha se faltar a licença ou a data de homologação.
- Os marcadores de página permitem citar "manual, p. N" na resposta.

## Livros em PDF

Um livro técnico inteiro tem de 60 mil a 200 mil tokens e não cabe na janela do
modelo. Por isso, o livro é extraído uma vez e cada bloco usa só os capítulos
daquele tema.

1. Extraia os livros (pode passar vários de uma vez):

   ```bash
   pip install -e ".[pdf]"
   ipeia ingerir ~/livros/*.pdf
   ```

   O comando lê o texto e o sumário (marcadores) do PDF, tira cabeçalhos, rodapés e
   hifenização, e mostra cada capítulo com o tamanho em tokens e o tema sugerido.
   No fim, imprime um esboço de `bloco.toml` por tema. PDF digitalizado (só imagem)
   precisa de OCR antes: `ocrmypdf -l por entrada.pdf saida.pdf`.

2. Preencha `fonte` e `licenca` em `_livros/<livro>/livro.toml`.

3. Revise o esboço e salve cada bloco em `<acervo>/<tema>/bloco.toml`:

   ```toml
   descricao = "Qualidade da água: oxigênio dissolvido, amônia, pH, alcalinidade, calagem, aeração"
   versao = "2026.11"

   [[manuais]]
   livro = "manual-tilapia"   # pasta em _livros/
   paginas = "31-58, 70-72"   # índices do PDF (1 = primeira folha do arquivo)
   homologado_em = "2026-11-10"
   ```

   `titulo`, `fonte` e `licenca` vêm do `livro.toml`, e a `versao` é o início do hash
   do PDF, a menos que o bloco informe outros valores. A resposta cita o número
   impresso na página, não o índice do PDF. A `descricao` é o que o roteador lê para
   escolher o bloco, então liste nela os assuntos e termos que o produtor usa.

4. Rode `ipeia verificar` e teste perguntas no `ipeia conversar`.

## Direitos autorais

O texto dos livros é protegido. `acervo/_livros/` e arquivos `.pdf` estão no
`.gitignore`: guarde o acervo real fora do repositório (aponte
`IPEIA_ACERVO_DIR` para a pasta) ou num repositório privado. Como o sistema envia
trechos literais aos produtores, o uso comercial exige licença de cada obra:
confira a licença das publicações da Embrapa uma a uma, e, para livros de editora,
inclusive os próprios, o contrato de edição.

**Os blocos `exemplo-*` são fictícios**, escritos só para testar o fluxo. Eles
não são manuais homologados e devem ser removidos antes de ir a campo.
