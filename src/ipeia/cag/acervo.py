"""Acervo técnico estático, dividido em blocos temáticos versionados (RF06, RNF05, RNF10).

Estrutura em disco:

    acervo/
      <bloco>/
        bloco.toml      # descrição, versão e lista de manuais
        <manual>.md     # texto do manual, com marcadores <!-- pagina: N -->
      _livros/
        <livro>/        # livros em PDF ingeridos com `ipeia ingerir` (ver ingestao.py)

Um manual do bloco pode ser um arquivo .md (`arquivo = ...`) ou um trecho de um
livro ingerido (`livro = ...` e `paginas = "31-58, 70"`).

Só o bloco escolhido pelo roteador entra no prompt. Como o prompt de sistema do
bloco é sempre o mesmo texto, o vLLM reaproveita o KV-Cache dele (RNF05).
"""

import re
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .ingestao import LICENCA_PENDENTE, interpretar_intervalos

_RE_PAGINA = re.compile(r"<!--\s*pagina:\s*(\S+?)(?:\s+pdf:\s*(\d+))?\s*-->", re.IGNORECASE)
PASTA_LIVROS = "_livros"
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
    indice_pdf: int | None = None


@dataclass(frozen=True)
class Manual:
    titulo: str
    fonte: str
    versao: str
    homologado_em: str
    licenca: str
    paginas: tuple[Pagina, ...]
    livro: str | None = None

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
    for numero, pdf, conteudo in zip(partes[1::3], partes[2::3], partes[3::3]):
        paginas.append(Pagina(numero, conteudo.strip(), normalizar_para_busca(conteudo),
                              int(pdf) if pdf else None))
    return tuple(paginas)


def _manual_de_livro(m: dict, pasta_livros: Path, bloco: str) -> Manual:
    pasta = pasta_livros / m["livro"]
    if not (pasta / "livro.md").exists():
        raise FileNotFoundError(
            f"Bloco {bloco}: livro {m['livro']!r} não encontrado em {pasta}. Rode `ipeia ingerir` "
            "com o PDF ou confira IPEIA_ACERVO_DIR.")
    with open(pasta / "livro.toml", "rb") as f:
        meta = tomllib.load(f)
    todas = _ler_paginas((pasta / "livro.md").read_text(encoding="utf-8"))
    por_indice = {p.indice_pdf: p for p in todas if p.indice_pdf is not None}
    escolhidas = interpretar_intervalos(m["paginas"], len(por_indice))
    paginas = tuple(por_indice[i] for i in escolhidas if por_indice[i].texto)
    return Manual(
        titulo=m.get("titulo") or meta.get("titulo", m["livro"]),
        fonte=m.get("fonte") or meta.get("fonte", ""),
        versao=str(m.get("versao") or meta.get("sha256", "")[:12]),
        homologado_em=str(m.get("homologado_em", "")),
        licenca=m.get("licenca") or meta.get("licenca", ""),
        paginas=paginas, livro=m["livro"],
    )


def carregar_bloco(pasta: Path, pasta_livros: Path | None = None) -> Bloco:
    pasta_livros = pasta_livros or pasta.parent / PASTA_LIVROS
    with open(pasta / "bloco.toml", "rb") as f:
        meta = tomllib.load(f)
    manuais = []
    for m in meta.get("manuais", []):
        if "livro" in m:
            manuais.append(_manual_de_livro(m, pasta_livros, pasta.name))
            continue
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

    def pendencias(self) -> list[str]:
        """Manuais sem licença conferida ou sem data de homologação (RNF10)."""
        avisos = []
        for b in self.blocos.values():
            for m in b.manuais:
                if not m.licenca.strip() or LICENCA_PENDENTE in m.licenca.lower():
                    avisos.append(f"{b.nome} / {m.titulo}: licença não conferida")
                if not m.homologado_em.strip():
                    avisos.append(f"{b.nome} / {m.titulo}: sem data de homologação")
        return avisos


def carregar_acervo(raiz: Path) -> Acervo:
    blocos = {}
    if raiz.exists():
        for pasta in sorted(p for p in raiz.iterdir() if (p / "bloco.toml").exists()):
            bloco = carregar_bloco(pasta)
            blocos[bloco.nome] = bloco
    return Acervo(blocos)
