"""Ingestão de livros em PDF para o acervo do CAG (RF06, RNF05, RNF10).

    ipeia ingerir livros/manual-tilapia.pdf

gera, em `<acervo>/_livros/<slug>/`:

    livro.md    texto limpo, com <!-- pagina: <rótulo impresso> pdf: <índice> --> antes de cada página
    livro.toml  metadados, hash do PDF, páginas sem texto e capítulos com tokens e temas sugeridos

O livro inteiro não entra no prompt (não caberia na janela do modelo). O
responsável técnico escolhe os capítulos de cada bloco temático no bloco.toml:

    [[manuais]]
    livro = "manual-tilapia"      # pasta em _livros/
    paginas = "31-58, 70-72"      # índices do PDF (1 = primeira folha do arquivo)
    homologado_em = "2026-11-10"
    licenca = "CC BY 4.0"         # ou o contrato de licença

As citações das respostas usam o número impresso na página, não o índice do PDF.
"""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .temas import GERAL, NOMES, sugerir_temas

MINIMO_CARACTERES_PAGINA = 40
PAGINAS_POR_SECAO_SEM_SUMARIO = 10
LICENCA_PENDENTE = "a conferir"


@dataclass(frozen=True)
class PaginaExtraida:
    indice: int  # 1 = primeira folha do PDF
    rotulo: str  # número impresso (ou romano), usado na citação
    texto: str


@dataclass(frozen=True)
class Capitulo:
    titulo: str
    inicio: int  # índice do PDF, inclusive
    fim: int  # índice do PDF, inclusive
    tokens: int
    temas: tuple[str, ...]

    @property
    def paginas(self) -> str:
        return f"{self.inicio}-{self.fim}" if self.fim > self.inicio else str(self.inicio)


@dataclass
class LivroExtraido:
    slug: str
    titulo: str
    arquivo_origem: str
    sha256: str
    paginas: list[PaginaExtraida]
    capitulos: list[Capitulo] = field(default_factory=list)

    @property
    def paginas_sem_texto(self) -> list[int]:
        return [p.indice for p in self.paginas if len(p.texto) < MINIMO_CARACTERES_PAGINA]

    @property
    def tokens_estimados(self) -> int:
        return sum(len(p.texto) for p in self.paginas) // 4


# ---------------------------------------------------------------- limpeza do texto

_RE_SO_NUMERO = re.compile(r"^\s*(\d{1,4}|[ivxlcdm]{1,7})\s*$", re.IGNORECASE)
_BORDA = 2  # linhas do topo e do rodapé onde procuramos cabeçalhos repetidos


def _chave(linha: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", linha.strip().lower()))


def limpar_paginas(brutas: list[str]) -> list[str]:
    """Tira cabeçalhos e rodapés repetidos e números de página soltos, junta palavras
    hifenizadas na quebra de linha e une as linhas de um mesmo parágrafo."""
    linhas = [[l for l in (t or "").splitlines() if l.strip()] for t in brutas]
    contagem: Counter[str] = Counter()
    for ls in linhas:
        contagem.update({_chave(l) for l in ls[:_BORDA] + ls[-_BORDA:]})
    minimo = max(3, int(0.3 * len(brutas)))
    repetidas = {k for k, n in contagem.items() if n >= minimo}

    limpas = []
    for ls in linhas:
        def descartar(i: int, l: str) -> bool:
            na_borda = i < _BORDA or i >= len(ls) - _BORDA
            return na_borda and (_chave(l) in repetidas or bool(_RE_SO_NUMERO.match(l)))

        texto = "\n".join(l.rstrip() for i, l in enumerate(ls) if not descartar(i, l))
        texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)  # oxi-\ngênio -> oxigênio
        texto = re.sub(r"(?<![.!?:;])\n(?=[a-zà-ÿ0-9(])", " ", texto)  # mesmo parágrafo
        texto = re.sub(r"[ \t]+", " ", texto).replace("<!--", "< !--").replace("-->", "-- >")
        limpas.append(texto.strip())
    return limpas


# ---------------------------------------------------------------- leitura do PDF

def gerar_slug(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "livro"


def _abrir_pdf(caminho: Path):
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise RuntimeError('Para ler PDFs, instale: pip install -e ".[pdf]"') from e
    return PdfReader(str(caminho))


def _itens_do_sumario(leitor) -> list[tuple[str, int]]:
    """Capítulos do sumário (marcadores) do PDF: nível 1, ou nível 2 se o 1 for só a capa."""
    niveis: dict[int, list[tuple[str, int]]] = {}

    def percorrer(itens, nivel: int) -> None:
        for item in itens:
            if isinstance(item, list):
                percorrer(item, nivel + 1)
                continue
            try:
                pagina = leitor.get_destination_page_number(item)
            except Exception:
                continue
            if pagina is not None and pagina >= 0:
                niveis.setdefault(nivel, []).append((str(item.title).strip(), pagina + 1))

    try:
        percorrer(leitor.outline, 0)
    except Exception:
        return []
    for nivel in sorted(niveis):
        if len(niveis[nivel]) >= 2:
            return sorted(niveis[nivel], key=lambda x: x[1])
    return []


def _montar_capitulos(paginas: list[PaginaExtraida], sumario: list[tuple[str, int]]) -> list[Capitulo]:
    total = len(paginas)
    if not sumario:
        sumario = [(f"Páginas {i}-{min(i + PAGINAS_POR_SECAO_SEM_SUMARIO - 1, total)}", i)
                   for i in range(1, total + 1, PAGINAS_POR_SECAO_SEM_SUMARIO)]
    elif sumario[0][1] > 1:
        sumario = [("Abertura (capa, créditos, sumário)", 1), *sumario]
    capitulos = []
    for n, (titulo, inicio) in enumerate(sumario):
        fim = sumario[n + 1][1] - 1 if n + 1 < len(sumario) else total
        fim = max(fim, inicio)
        texto = "\n".join(p.texto for p in paginas[inicio - 1:fim])
        capitulos.append(Capitulo(titulo, inicio, fim, len(texto) // 4, tuple(sugerir_temas(texto))))
    return capitulos


def extrair_pdf(caminho: Path, slug: str | None = None) -> LivroExtraido:
    caminho = Path(caminho)
    leitor = _abrir_pdf(caminho)
    try:
        rotulos = list(leitor.page_labels)
    except Exception:
        rotulos = []
    brutas = []
    for pagina in leitor.pages:
        try:
            brutas.append(pagina.extract_text() or "")
        except Exception:
            brutas.append("")
    textos = limpar_paginas(brutas)
    paginas = [PaginaExtraida(i, re.sub(r"\s+", "_", rotulos[i - 1]) if i <= len(rotulos) and rotulos[i - 1]
                              else str(i), t) for i, t in enumerate(textos, 1)]
    titulo = ""
    try:
        titulo = (leitor.metadata.title or "") if leitor.metadata else ""
    except Exception:
        pass
    livro = LivroExtraido(
        slug=slug or gerar_slug(caminho.stem), titulo=titulo.strip() or caminho.stem,
        arquivo_origem=caminho.name, sha256=hashlib.sha256(caminho.read_bytes()).hexdigest(),
        paginas=paginas,
    )
    livro.capitulos = _montar_capitulos(paginas, _itens_do_sumario(leitor))
    return livro


# ---------------------------------------------------------------- gravação

def _toml(valor) -> str:
    # Strings JSON são strings básicas TOML válidas.
    return json.dumps(valor, ensure_ascii=False)


def gravar_livro(livro: LivroExtraido, destino: Path) -> Path:
    pasta = Path(destino) / livro.slug
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "livro.md").write_text(
        "".join(f"<!-- pagina: {p.rotulo} pdf: {p.indice} -->\n{p.texto}\n\n" for p in livro.paginas),
        encoding="utf-8")

    linhas = [
        f"titulo = {_toml(livro.titulo)}",
        f"arquivo_origem = {_toml(livro.arquivo_origem)}",
        f"sha256 = {_toml(livro.sha256)}",
        f"extraido_em = {_toml(date.today().isoformat())}",
        f"paginas_pdf = {len(livro.paginas)}",
        f"tokens_estimados = {livro.tokens_estimados}",
        f"paginas_sem_texto = {_toml(livro.paginas_sem_texto)}",
        "",
        "# Preencha antes de usar em produção (RNF10). Os blocos herdam estes valores.",
        'fonte = ""            # autores, editora, ano',
        f"licenca = {_toml(LICENCA_PENDENTE)}   # ex.: CC BY 4.0, contrato com a editora, obra própria",
        "",
    ]
    for c in livro.capitulos:
        linhas += ["[[capitulos]]", f"titulo = {_toml(c.titulo)}", f"paginas = {_toml(c.paginas)}",
                   f"tokens = {c.tokens}", f"temas = {_toml(list(c.temas))}", ""]
    (pasta / "livro.toml").write_text("\n".join(linhas), encoding="utf-8")
    return pasta


# ---------------------------------------------------------------- sugestão de blocos

def agrupar_por_tema(livros: list[LivroExtraido]) -> dict[str, list[tuple[LivroExtraido, Capitulo]]]:
    """Agrupa os capítulos pelo tema principal sugerido. "geral" fica de fora."""
    grupos: dict[str, list[tuple[LivroExtraido, Capitulo]]] = {}
    for livro in livros:
        for cap in livro.capitulos:
            tema = cap.temas[0]
            if tema != GERAL:
                grupos.setdefault(tema, []).append((livro, cap))
    return grupos


def _juntar_intervalos(caps: list[Capitulo]) -> str:
    intervalos: list[list[int]] = []
    for c in sorted(caps, key=lambda c: c.inicio):
        if intervalos and c.inicio <= intervalos[-1][1] + 1:
            intervalos[-1][1] = max(intervalos[-1][1], c.fim)
        else:
            intervalos.append([c.inicio, c.fim])
    return ", ".join(f"{a}-{b}" if b > a else str(a) for a, b in intervalos)


def esboco_bloco_toml(tema: str, itens: list[tuple[LivroExtraido, Capitulo]]) -> str:
    """Texto pronto para revisar e salvar como <acervo>/<tema>/bloco.toml."""
    por_livro: dict[str, tuple[LivroExtraido, list[Capitulo]]] = {}
    for livro, cap in itens:
        por_livro.setdefault(livro.slug, (livro, []))[1].append(cap)
    linhas = [f'descricao = "{NOMES.get(tema, tema)}: <liste os assuntos, o roteador escolhe o bloco por eles>"',
              f'versao = "{date.today():%Y.%m}"', ""]
    for slug, (livro, caps) in por_livro.items():
        linhas += ["[[manuais]]", f"livro = {_toml(slug)}",
                   f"paginas = {_toml(_juntar_intervalos(caps))}",
                   "# " + "; ".join(c.titulo for c in caps),
                   'homologado_em = ""   # data em que o responsável técnico revisou', ""]
    return "\n".join(linhas)


# ---------------------------------------------------------------- uso nos blocos

def interpretar_intervalos(texto: str, total: int) -> list[int]:
    """'31-58, 70' -> [31, ..., 58, 70], conferindo os limites do livro."""
    indices: list[int] = []
    for parte in (p.strip() for p in str(texto).split(",")):
        if not parte:
            continue
        m = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", parte)
        if not m:
            raise ValueError(f"Intervalo de páginas inválido: {parte!r}")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if not 1 <= a <= b <= total:
            raise ValueError(f"Páginas {parte} fora do livro (1-{total})")
        indices.extend(range(a, b + 1))
    if not indices:
        raise ValueError("Nenhuma página selecionada")
    return sorted(set(indices))
