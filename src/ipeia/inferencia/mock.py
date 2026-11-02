"""Implementações falsas para rodar e testar tudo localmente, sem GPU.

O `ModeloMock` imita o Amadeus-Verbo com expressões regulares simples. Ele
reconhece a tarefa pelo `title` do esquema JSON e devolve uma saída que
obedece ao mesmo esquema que o modelo real receberia. Não serve para medir
acurácia (isso é o RNF01, com áudios reais); serve para exercitar o fluxo.
"""

import re
import unicodedata
from typing import Any

from .base import Transcricao

_NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4,
            "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "meio": 0.5,
            "meia": 0.5}

_PALAVRAS_VAZIAS = {"para", "como", "qual", "quais", "quando", "quanto", "deve", "devo", "pode",
                    "posso", "fazer", "esta", "está", "isso", "essa", "esse", "minha", "meus",
                    "tanque", "peixe", "peixes", "sobre", "entre", "mais", "menos", "muito"}


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))


def _numero(token: str) -> float:
    token = token.lower()
    if token in _NUMEROS:
        return float(_NUMEROS[token])
    return float(token.replace(",", "."))


def _sentencas(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.?!])\s+", texto.strip())
    return [p.strip() for p in partes if p.strip()]


def _intencao(sentenca: str) -> str:
    s = _sem_acento(sentenca.lower())
    if re.search(r"corrig|errei|na verdade|nao foi|estorn|cancela o|apaga o|\bo de (?:hoje|ontem)\b|, nao \d", s):
        return "correcao"
    if s.endswith("?") or re.match(r"(como|qual|quais|quando|por que|porque|o que|quanto|devo|posso)\b", s):
        return "consulta"
    if re.search(r"racao|\bkg\b|quilo|saco|morr|mort[oa]s?\b|tratei|\bdei\b|joguei|arracoa", s):
        return "manejo"
    return "outro"


def _roteamento(texto: str) -> dict[str, Any]:
    segmentos: list[dict[str, str]] = []
    for sentenca in _sentencas(texto):
        intencao = _intencao(sentenca)
        if segmentos and segmentos[-1]["intencao"] == intencao:
            segmentos[-1]["texto"] += " " + sentenca
        else:
            segmentos.append({"intencao": intencao, "texto": sentenca})
    return {"segmentos": segmentos or [{"intencao": "outro", "texto": texto}]}


_RE_TANQUE = re.compile(r"\b(?:tanque|viveiro)\s+((?:d[aoe]s?\s+)?[\w-]+)", re.IGNORECASE)
_RE_QTD = re.compile(
    r"\b(\d+(?:[.,]\d+)?|meio|meia|uma?|dois|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez)"
    r"\s*(kg|quilos?|kilos?|gramas?|g|sacos?)\b", re.IGNORECASE)
_RE_MORTOS = [
    re.compile(r"\b(\d+|uma?|dois|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez)\s+(?:peixes?\s+)?(?:mort[oa]s?|morreram)", re.IGNORECASE),
    re.compile(r"\bmorreram\s+(\d+|uma?|dois|duas|tr[eê]s|quatro|cinco)", re.IGNORECASE),
    re.compile(r"\bmortalidade\s+(?:de\s+)?(\d+)", re.IGNORECASE),
]
_RE_SEM_MORTOS = re.compile(r"nenhum (?:peixe )?morto|sem mortalidade|n[aã]o morreu", re.IGNORECASE)
_RE_TIPO = re.compile(r"ra[cç][aã]o\s+(?:de\s+)?(\d+\s*mm|\d+\s*%|inicial|crescimento|engorda|alevin\w*|juvenil)",
                      re.IGNORECASE)
_RE_HORA = re.compile(r"\b[àa]s?\s+(\d{1,2})(?:[:h](\d{2}))?\s*(?:h|horas?)?\b", re.IGNORECASE)


def _unidade(token: str) -> str:
    token = token.lower()
    if token.startswith("saco"):
        return "saco"
    if token.startswith("g"):
        return "g"
    return "kg"


def _item(trecho: str, tanque: str, texto_completo: str) -> dict[str, Any]:
    item: dict[str, Any] = {"tanque": tanque, "quantidade_racao": None, "unidade_racao": None,
                            "tipo_racao": None, "mortalidade": None, "hora_manejo": None,
                            "dias_atras": None}
    if m := _RE_QTD.search(trecho):
        item["quantidade_racao"] = _numero(m.group(1))
        item["unidade_racao"] = _unidade(m.group(2))
    for padrao in _RE_MORTOS:
        if m := padrao.search(trecho):
            item["mortalidade"] = int(_numero(m.group(1)))
            break
    else:
        if _RE_SEM_MORTOS.search(trecho):
            item["mortalidade"] = 0
    if m := _RE_TIPO.search(trecho):
        item["tipo_racao"] = m.group(1).strip()
    if m := (_RE_HORA.search(trecho) or _RE_HORA.search(texto_completo)):
        item["hora_manejo"] = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    baixo = _sem_acento(texto_completo.lower())
    if "anteontem" in baixo:
        item["dias_atras"] = 2
    elif "ontem" in baixo:
        item["dias_atras"] = 1
    return item


def _extracao(texto: str) -> dict[str, Any]:
    ocorrencias = list(_RE_TANQUE.finditer(texto))
    if not ocorrencias:
        return {"itens": []}
    # Decide se a quantidade vem antes ("dei 30 kg no tanque 3") ou depois
    # ("no tanque 3 dei 30 kg") do tanque, olhando a primeira ocorrência.
    primeira_qtd = _RE_QTD.search(texto) or _RE_MORTOS[0].search(texto)
    antes = bool(primeira_qtd and primeira_qtd.start() < ocorrencias[0].start())
    itens = []
    for i, m in enumerate(ocorrencias):
        if len(ocorrencias) == 1:
            trecho = texto
        elif antes:
            inicio = ocorrencias[i - 1].end() if i > 0 else 0
            trecho = texto[inicio:m.start()]
        else:
            fim = ocorrencias[i + 1].start() if i + 1 < len(ocorrencias) else len(texto)
            trecho = texto[m.end():fim]
        itens.append(_item(trecho, m.group(0).strip(), texto))
    return {"itens": itens}


def _correcao(texto: str) -> dict[str, Any]:
    tanques = _RE_TANQUE.findall(texto)
    item = _item(texto, f"tanque {tanques[0]}" if tanques else "", texto)
    acao = "estornar" if re.search(r"estorn|cancela|apaga", _sem_acento(texto.lower())) else "corrigir"
    return {"acao": acao, "tanque": item["tanque"], "dias_atras": item["dias_atras"],
            "quantidade_racao": item["quantidade_racao"], "unidade_racao": item["unidade_racao"],
            "mortalidade": item["mortalidade"]}


def _palavras(texto: str) -> set[str]:
    return {p for p in re.findall(r"\w+", _sem_acento(texto.lower()))
            if len(p) > 3 and p not in _PALAVRAS_VAZIAS}


def _escolha_bloco(sistema: str, pergunta: str, opcoes: list[str]) -> dict[str, Any]:
    alvo = _palavras(pergunta)
    melhor, pontos = "nenhum", 0
    for opcao in opcoes:
        if opcao == "nenhum":
            continue
        descricao = re.search(rf"^- {re.escape(opcao)}: (.*)$", sistema, re.MULTILINE)
        texto = opcao.replace("-", " ") + " " + (descricao.group(1) if descricao else "")
        p = len(alvo & _palavras(texto))
        if p > pontos:
            melhor, pontos = opcao, p
    return {"bloco": melhor}


def _resposta_tecnica(sistema: str, pergunta: str) -> dict[str, Any]:
    acervo = re.search(r"<acervo>(.*)</acervo>", sistema, re.DOTALL)
    texto = re.sub(r"<!--.*?-->", " ", acervo.group(1) if acervo else "", flags=re.DOTALL)
    alvo = _palavras(pergunta)
    melhor, pontos = "", 0
    for linha in texto.splitlines():
        for sentenca in _sentencas(linha.strip().lstrip("#-* ")):
            p = len(alvo & _palavras(sentenca))
            if p > pontos:
                melhor, pontos = sentenca, p
    if pontos < 2:
        return {"encontrado": False, "resposta": "", "citacao_literal": ""}
    return {"encontrado": True, "resposta": f"Segundo o manual: {melhor}", "citacao_literal": melhor}


class ModeloMock:
    """Imitação determinística do Amadeus-Verbo para desenvolvimento."""

    def __init__(self):
        self.chamadas: list[dict[str, Any]] = []

    def gerar_json(self, sistema: str, usuario: str, esquema: dict[str, Any]) -> dict[str, Any]:
        tarefa = esquema.get("title")
        self.chamadas.append({"tarefa": tarefa, "usuario": usuario})
        if tarefa == "roteamento":
            return _roteamento(usuario)
        if tarefa == "extracao_manejo":
            return _extracao(usuario)
        if tarefa == "correcao":
            return _correcao(usuario)
        if tarefa == "escolha_bloco":
            return _escolha_bloco(sistema, usuario, esquema["properties"]["bloco"]["enum"])
        if tarefa == "resposta_tecnica":
            return _resposta_tecnica(sistema, usuario)
        raise ValueError(f"Tarefa desconhecida para o mock: {tarefa}")


class TranscritorMock:
    """Trata os bytes do "áudio" como texto UTF-8. Ótimo para testes.

    Um áudio que comece com `#baixa#` simula uma transcrição de baixa confiança.
    """

    def transcrever(self, audio: bytes, mime: str = "audio/ogg") -> Transcricao:
        texto = audio.decode("utf-8", errors="ignore").strip()
        if texto.startswith("#baixa#"):
            return Transcricao(texto=texto.removeprefix("#baixa#").strip(), confianca=0.3)
        return Transcricao(texto=texto, confianca=0.95 if texto else 0.0)
