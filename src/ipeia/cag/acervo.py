"""Acervo técnico estático, dividido em blocos temáticos versionados (RF06, RNF05, RNF10).

Estrutura em disco:

    acervo/
      <bloco>/
        bloco.toml      # descrição, versão e lista de manuais
        <manual>.md     # texto do manual, com marcadores <!-- pagina: N -->

Só o bloco escolhido pelo roteador entra no prompt. Como o prompt de sistema do
bloco é sempre o mesmo texto, o vLLM reaproveita o KV-Cache dele (RNF05).
"""

import re
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_RE_PAGINA = re.compile(r"<!--\s*pagina:\s*(\S+)\s*-->", re.IGNORECASE)
TAMANHO_MINIMO_CITACAO = 20


def normalizar_para_busca(texto: str) -> str:
    s = unicodedata.normalize("NFKC", texto).lower()
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = re.sub(r"[*_#>`|]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .;:,\"'")


@dataclass(frozen=True)
class Pagina:
    numero: str
    texto: str
    normalizado: str


@dataclass(frozen=True)
class Manual:
    titulo: str
    fonte: str
    versao: str
    homologado_em: str
    licenca: str
    paginas: tuple[Pagina, ...]

    @property
    def texto(self) -> str:
        return "\n".join(f"<!-- pagina: {p.numero} -->\n{p.texto}" for p in self.paginas)


@dataclass(frozen=True)
class Localizacao:
    manual: Manual
    pagina: str


@dataclass(frozen=True)
class Bloco:
    nome: str
    descricao: str
    versao: str
    manuais: tuple[Manual, ...]

    @property
    def versao_completa(self) -> str:
        return f"{self.nome}@{self.versao}"

    def texto_para_prompt(self) -> str:
        partes = []
        for m in self.manuais:
            partes.append(f'<manual titulo="{m.titulo}" fonte="{m.fonte}" versao="{m.versao}">\n'
                          f"{m.texto}\n</manual>")
        return "\n\n".join(partes)

    def localizar(self, citacao: str) -> Localizacao | None:
        """Barreira de citação (RNF03): o trecho tem de existir literalmente no bloco."""
        alvo = normalizar_para_busca(citacao)
        if len(alvo) < TAMANHO_MINIMO_CITACAO:
            return None
        for manual in self.manuais:
            for pagina in manual.paginas:
                if alvo in pagina.normalizado:
                    return Localizacao(manual, pagina.numero)
        return None

    def tokens_estimados(self) -> int:
        """Estimativa grosseira (4 caracteres por token). Meça com o tokenizer real."""
        return len(self.texto_para_prompt()) // 4


def _ler_paginas(texto: str) -> tuple[Pagina, ...]:
    partes = _RE_PAGINA.split(texto)
    paginas: list[Pagina] = []
    if partes[0].strip():
        paginas.append(Pagina("?", partes[0].strip(), normalizar_para_busca(partes[0])))
    for numero, conteudo in zip(partes[1::2], partes[2::2]):
        paginas.append(Pagina(numero, conteudo.strip(), normalizar_para_busca(conteudo)))
    return tuple(paginas)


def carregar_bloco(pasta: Path) -> Bloco:
    with open(pasta / "bloco.toml", "rb") as f:
        meta = tomllib.load(f)
    manuais = []
    for m in meta.get("manuais", []):
        texto = (pasta / m["arquivo"]).read_text(encoding="utf-8")
        manuais.append(Manual(titulo=m["titulo"], fonte=m.get("fonte", ""), versao=str(m["versao"]),
                              homologado_em=str(m.get("homologado_em", "")),
                              licenca=m.get("licenca", ""), paginas=_ler_paginas(texto)))
    return Bloco(nome=pasta.name, descricao=meta["descricao"], versao=str(meta["versao"]),
                 manuais=tuple(manuais))


@dataclass(frozen=True)
class Acervo:
    blocos: dict[str, Bloco]

    def verificar_tamanho(self, janela_tokens: int) -> list[str]:
        """Lista os blocos que passam de metade da janela de contexto (RNF05)."""
        limite = janela_tokens // 2
        return [f"{b.nome}: ~{b.tokens_estimados()} tokens (limite {limite})"
                for b in self.blocos.values() if b.tokens_estimados() > limite]


def carregar_acervo(raiz: Path) -> Acervo:
    blocos = {}
    if raiz.exists():
        for pasta in sorted(p for p in raiz.iterdir() if (p / "bloco.toml").exists()):
            bloco = carregar_bloco(pasta)
            blocos[bloco.nome] = bloco
    return Acervo(blocos)
