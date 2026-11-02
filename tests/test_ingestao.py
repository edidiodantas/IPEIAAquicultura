"""Ingestão de livros em PDF e uso de trechos de livros nos blocos do CAG."""

import pytest

pypdf = pytest.importorskip("pypdf")
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject  # noqa: E402

from ipeia.cag.acervo import carregar_acervo  # noqa: E402
from ipeia.cag.consulta import responder  # noqa: E402
from ipeia.cag.ingestao import (  # noqa: E402
    agrupar_por_tema, esboco_bloco_toml, extrair_pdf, gravar_livro, interpretar_intervalos,
)
from ipeia.cag.textos import AVISO_LEGAL  # noqa: E402
from ipeia.inferencia.mock import ModeloMock  # noqa: E402

CABECALHO = "Manual de Piscicultura de Teste"
PAGINAS = [
    "Manual de Piscicultura de Teste\nCapa",
    "Manual de Piscicultura de Teste\nApresentação do livro, escrita para os testes do sistema.\nii",
    "Manual de Piscicultura de Teste\nCapítulo 1. Qualidade da água\nO oxi-\ngênio dissolvido deve ficar "
    "acima de 4 mg/L nos viveiros de\ntilápia durante todo o ciclo.\nA amônia tóxica sobe quando o pH "
    "passa de 8,5.\n1",
    "Manual de Piscicultura de Teste\nUse aeração noturna quando o oxigênio cair e confira a "
    "alcalinidade\ne a amônia toda semana.\n2",
    "Manual de Piscicultura de Teste\nCapítulo 2. Doenças\nPeixes com manchas, lesões ou natação errática "
    "indicam doença.\nSepare os peixes doentes e chame o técnico antes de qualquer tratamento.\n3",
    "",  # folha em branco (ou figura digitalizada)
]


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _criar_pdf(caminho):
    w = pypdf.PdfWriter()
    fonte = w._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    }))
    for texto in PAGINAS:
        pagina = w.add_blank_page(595, 842)
        ops = ["BT /F1 11 Tf 14 TL 50 800 Td"] + [f"({_escapar(l)}) Tj T*" for l in texto.split("\n") if l]
        conteudo = DecodedStreamObject()
        conteudo.set_data("\n".join(ops + ["ET"]).encode("cp1252"))
        pagina[NameObject("/Contents")] = w._add_object(conteudo)
        pagina[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): fonte})})
    w.set_page_label(0, 1, "/r")
    w.set_page_label(2, 5, "/D", start=1)
    w.add_outline_item("Capítulo 1. Qualidade da água", 2)
    w.add_outline_item("Capítulo 2. Doenças", 4)
    w.add_metadata({"/Title": "Manual de Piscicultura de Teste"})
    w.write(str(caminho))


@pytest.fixture
def livro(tmp_path):
    _criar_pdf(tmp_path / "manual-teste.pdf")
    return extrair_pdf(tmp_path / "manual-teste.pdf")


def test_extracao_limpa_o_texto(livro):
    assert livro.slug == "manual-teste" and livro.titulo == CABECALHO
    textos = [p.texto for p in livro.paginas]
    assert not any(CABECALHO in t for t in textos)  # cabeçalho repetido removido
    assert "oxigênio dissolvido deve ficar acima de 4 mg/L nos viveiros de tilápia" in textos[2]
    assert not textos[2].endswith("1")  # número de página solto removido
    assert [p.rotulo for p in livro.paginas[:4]] == ["i", "ii", "1", "2"]
    assert livro.paginas_sem_texto == [1, 6]


def test_capitulos_do_sumario_com_temas(livro):
    titulos = [(c.titulo, c.paginas) for c in livro.capitulos]
    assert titulos == [("Abertura (capa, créditos, sumário)", "1-2"),
                       ("Capítulo 1. Qualidade da água", "3-4"), ("Capítulo 2. Doenças", "5-6")]
    assert livro.capitulos[1].temas[0] == "qualidade-agua"
    assert livro.capitulos[2].temas[0] == "sanidade"
    grupos = agrupar_por_tema([livro])
    assert set(grupos) == {"qualidade-agua", "sanidade"}
    assert 'paginas = "3-4"' in esboco_bloco_toml("qualidade-agua", grupos["qualidade-agua"])


def test_bloco_com_trecho_de_livro_responde_com_pagina_impressa(livro, tmp_path):
    acervo_dir = tmp_path / "acervo"
    gravar_livro(livro, acervo_dir / "_livros")
    (acervo_dir / "qualidade-agua").mkdir()
    (acervo_dir / "qualidade-agua" / "bloco.toml").write_text(
        'descricao = "Qualidade da água: oxigênio, amônia, pH"\nversao = "2026.11"\n\n'
        '[[manuais]]\nlivro = "manual-teste"\npaginas = "3-4"\nhomologado_em = "2026-11-02"\n'
        'licenca = "obra própria"\n', encoding="utf-8")

    acervo = carregar_acervo(acervo_dir)
    bloco = acervo.blocos["qualidade-agua"]
    manual = bloco.manuais[0]
    assert manual.titulo == CABECALHO and len(manual.versao) == 12  # versão = hash do PDF
    assert "Doenças" not in bloco.texto_para_prompt()  # só as páginas escolhidas entram

    r = responder(ModeloMock(), acervo, "Qual o oxigênio dissolvido mínimo nos viveiros de tilápia?")
    assert r.verificada and "p. 1" in r.texto and r.texto.endswith(AVISO_LEGAL)
    assert acervo.pendencias() == []


def test_licenca_pendente_e_herdada_do_livro(livro, tmp_path):
    acervo_dir = tmp_path / "acervo"
    gravar_livro(livro, acervo_dir / "_livros")
    (acervo_dir / "sanidade").mkdir()
    (acervo_dir / "sanidade" / "bloco.toml").write_text(
        'descricao = "Doenças"\nversao = "1"\n\n[[manuais]]\nlivro = "manual-teste"\npaginas = "5"\n',
        encoding="utf-8")
    pend = carregar_acervo(acervo_dir).pendencias()
    assert any("licença não conferida" in p for p in pend)
    assert any("sem data de homologação" in p for p in pend)


def test_livro_ausente_tem_mensagem_clara(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "bloco.toml").write_text(
        'descricao = "x"\nversao = "1"\n[[manuais]]\nlivro = "nao-existe"\npaginas = "1"\n')
    with pytest.raises(FileNotFoundError, match="ipeia ingerir"):
        carregar_acervo(tmp_path)


def test_intervalos_de_paginas():
    assert interpretar_intervalos("3-5, 8, 4", 10) == [3, 4, 5, 8]
    with pytest.raises(ValueError, match="fora do livro"):
        interpretar_intervalos("9-12", 10)
    with pytest.raises(ValueError):
        interpretar_intervalos("três", 10)
