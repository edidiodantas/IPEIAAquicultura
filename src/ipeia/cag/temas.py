"""Temas dos blocos do acervo e sugestão automática de tema por capítulo (RF06, RNF05).

A sugestão é só um ponto de partida: quem decide em que bloco cada capítulo
entra é o responsável técnico, ao montar o bloco.toml.
"""

import re
import unicodedata

# Tema -> palavras-chave (sem acento, minúsculas). Raízes curtas pegam plural e flexões.
TEMAS: dict[str, tuple[str, ...]] = {
    "qualidade-agua": (
        "oxigenio", "amonia", "nitrito", "nitrato", "ph", "alcalinidade", "dureza", "transparencia",
        "calagem", "calcario", "aeracao", "aerador", "fitoplancton", "temperatura da agua",
        "qualidade da agua", "renovacao de agua", "turbidez", "gas carbonico",
    ),
    "sanidade": (
        "doenca", "parasit", "bacteri", "virus", "fung", "sintoma", "sinais clinicos", "mortalidade",
        "quarentena", "vacina", "tratamento", "antibiotic", "sanitari", "patogen", "lesao", "lesoes",
        "estreptococ", "ictio", "branquia", "necropsia", "biosseguranca",
    ),
    "nutricao": (
        "racao", "proteina", "arracoamento", "alimentacao", "conversao alimentar", "nutri",
        "energia digestivel", "lipidi", "vitamina", "taxa de alimentacao", "pelete", "extrusad",
    ),
    "reproducao": (
        "reproducao", "reprodutor", "matriz", "desova", "larva", "alevin", "pos-larva", "incubacao",
        "reversao sexual", "hormoni", "hipofis", "ovos", "fertilizacao", "eclosao",
    ),
    "manejo-producao": (
        "povoamento", "densidade de estocagem", "biometria", "despesca", "transporte", "viveiro",
        "tanque-rede", "tanques-rede", "engorda", "recria", "ciclo de producao", "classificacao",
        "biomassa", "estocagem",
    ),
    "gestao": (
        "custo", "receita", "lucro", "comercializacao", "mercado", "preco", "investimento",
        "licenciamento", "outorga", "legislacao", "planejamento", "rentabilidade",
    ),
}

NOMES = {
    "qualidade-agua": "Qualidade da água", "sanidade": "Sanidade e doenças", "nutricao": "Nutrição e alimentação",
    "reproducao": "Reprodução e alevinagem", "manejo-producao": "Manejo da produção", "gestao": "Gestão e economia",
}

GERAL = "geral"
MINIMO_OCORRENCIAS = 3


def _sem_acento(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _contar(texto: str, termo: str) -> int:
    # Termos curtos ("ph") só valem como palavra inteira; os demais, como início de palavra.
    padrao = rf"\b{re.escape(termo)}\b" if len(termo) <= 3 else rf"\b{re.escape(termo)}"
    return len(re.findall(padrao, texto))


def pontuar_temas(texto: str) -> dict[str, int]:
    alvo = _sem_acento(texto)
    return {tema: sum(_contar(alvo, t) for t in termos) for tema, termos in TEMAS.items()}


def sugerir_temas(texto: str) -> list[str]:
    """Tema principal primeiro, mais os que tiverem ao menos metade da pontuação dele."""
    pontos = pontuar_temas(texto)
    maior = max(pontos.values(), default=0)
    if maior < MINIMO_OCORRENCIAS:
        return [GERAL]
    return [t for t, p in sorted(pontos.items(), key=lambda kv: -kv[1]) if p >= max(maior / 2, 1)]
