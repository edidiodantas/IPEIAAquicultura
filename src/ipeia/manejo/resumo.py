"""Textos enviados ao produtor no fluxo de manejo (RF02, RF05)."""

from zoneinfo import ZoneInfo

from ..formatacao import num
from ..banco.modelos import Lancamento, Pendencia, TipoLancamento
from ..tempo import como_utc


def _descrever(l: Lancamento, fuso: str) -> str:
    """Uma linha por lançamento: 'T3: 30 kg de ração (4 mm), 2 mortos, 02/11 às 07:00'."""
    partes = []
    if l.racao_kg is not None:
        partes.append(f"{num(l.racao_kg)} kg de ração" + (f" ({l.tipo_racao})" if l.tipo_racao else ""))
    if l.mortalidade is not None:
        partes.append("nenhum morto" if l.mortalidade == 0 else
                      f"{l.mortalidade} morto" + ("s" if l.mortalidade > 1 else ""))
    quando = como_utc(l.manejo_em).astimezone(ZoneInfo(fuso)).strftime("%d/%m às %H:%M")
    prefixo = "↩️ Estornar" if l.tipo == TipoLancamento.estorno else "•"
    return f"{prefixo} {l.tanque.codigo}: {', '.join(partes)}, {quando}"


def texto_resumo(ctx, texto_original: str, pendencia: Pendencia) -> str:
    linhas = ["📋 Entendi assim:", f"🗣️ “{texto_original.strip()}”", ""]
    linhas += [_descrever(l, ctx.cfg.fuso_horario) for l in pendencia.lancamentos]
    alertas = [m for l in pendencia.lancamentos for m in (l.validacao or {}).get("mensagens", [])]
    if alertas:
        linhas += ["", "⚠️ Fora do usual:"] + [f"- {a}" for a in alertas]
        linhas += ["", "Se estiver certo, toque em Confirmar e diga o motivo."]
    linhas += ["", "Está correto? (vale por 24 horas)"]
    return "\n".join(linhas)


def texto_bloqueio(problemas: list[str]) -> str:
    return "\n".join(["🚫 Não registrei nada desta mensagem:", *[f"- {p}" for p in problemas], "",
                      "Corrija e envie de novo."])
