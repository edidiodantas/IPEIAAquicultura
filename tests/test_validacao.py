from ipeia.manejo.unidades import para_kg
from ipeia.manejo.validacao import ContextoLote, Nivel, validar

# Lote de tilápia em engorda: 1.500 peixes x 500 g = 750 kg de biomassa.
ENGORDA = ContextoLote(especie="tilapia", fase="engorda", quantidade_atual=1500, peso_medio_g=500)


def item(**kw):
    return {"tanque_codigo": "T2", **kw}


def test_ok(limites):
    r = validar(item(racao_kg=15, mortalidade=2), limites, ENGORDA)
    assert r.nivel == Nivel.ok and r.mensagens == []


def test_alerta_racao(limites):
    # 30 kg = 4% da biomassa; o alerta da engorda é 3%.
    r = validar(item(racao_kg=30), limites, ENGORDA)
    assert r.nivel == Nivel.alerta and "4,0% da biomassa" in r.mensagens[0]


def test_soma_do_dia(limites):
    # 15 kg agora + 10 kg já dados = 25 kg = 3,3%: alerta.
    assert validar(item(racao_kg=15), limites, ENGORDA, racao_no_dia_kg=10).nivel == Nivel.alerta


def test_bloqueio_racao(limites):
    r = validar(item(racao_kg=100), limites, ENGORDA)  # 13,3% > 10%
    assert r.nivel == Nivel.bloqueio


def test_bloqueio_mortalidade_maior_que_lote(limites):
    r = validar(item(mortalidade=2000), limites, ENGORDA)
    assert r.nivel == Nivel.bloqueio and "1500 peixes" in r.mensagens[0]


def test_alerta_mortalidade(limites):
    r = validar(item(mortalidade=30), limites, ENGORDA)  # 2% > 1%
    assert r.nivel == Nivel.alerta


def test_sem_dados(limites):
    assert validar(item(), limites, ENGORDA).nivel == Nivel.bloqueio


def test_negativo(limites):
    assert validar(item(racao_kg=-5), limites, ENGORDA).nivel == Nivel.bloqueio


def test_sem_lote(limites):
    assert validar(item(racao_kg=10), limites, None).nivel == Nivel.alerta
    assert validar(item(racao_kg=500), limites, None).nivel == Nivel.bloqueio
    assert validar(item(mortalidade=3), limites, None).nivel == Nivel.bloqueio


def test_especie_sem_limites(limites):
    lote = ENGORDA.model_copy(update={"especie": "pirarucu"})
    r = validar(item(racao_kg=10), limites, lote)
    assert r.nivel == Nivel.alerta and "validação foi parcial" in r.mensagens[0]


def test_unidades():
    assert para_kg(0.5, "saco", 25) == 12.5
    assert para_kg(500, "g", 25) == 0.5
    assert para_kg(3, "kg", 25) == 3
    assert para_kg(None, "kg", 25) is None
