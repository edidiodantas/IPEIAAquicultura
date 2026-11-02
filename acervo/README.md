# Acervo técnico (CAG)

Cada pasta é um **bloco temático** (RF06, RNF05). Só o bloco escolhido pelo
roteador entra no prompt, e o vLLM mantém esse prefixo em KV-Cache.

```
acervo/<bloco>/bloco.toml   descrição, versão e lista de manuais do bloco
acervo/<bloco>/<manual>.md  texto do manual, com <!-- pagina: N --> antes de cada página
```

Regras:

- Cada bloco deve caber em até metade da janela de contexto do modelo. Confira com `ipeia verificar`.
- Todo manual precisa de `versao`, `homologado_em` e `licenca` (RNF10). Confira a licença antes de incluir.
- Os marcadores de página permitem citar "manual, p. N" na resposta.

**Os blocos `exemplo-*` são fictícios**, escritos só para testar o fluxo. Eles
não são manuais homologados e devem ser removidos antes de ir a campo.
