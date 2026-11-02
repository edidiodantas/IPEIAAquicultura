"""Cadastro da propriedade (RF09): fazenda, tanques, apelidos, lotes e usuários.

O painel web (ou o cadastro pelo WhatsApp) ainda não existe; estas funções são
a base que ele vai usar. `criar_fazenda_demo` monta uma fazenda de exemplo
para testes e para o simulador local.
"""

from sqlalchemy.orm import Session

from .banco.modelos import ApelidoTanque, Fazenda, Lote, Tanque, Usuario
from .manejo.apelidos import normalizar
from .tempo import agora_utc


def criar_fazenda(sessao: Session, nome: str, peso_saco_kg: float = 25.0) -> Fazenda:
    fazenda = Fazenda(nome=nome, peso_saco_kg=peso_saco_kg)
    sessao.add(fazenda)
    sessao.flush()
    return fazenda


def adicionar_tanque(sessao: Session, fazenda: Fazenda, codigo: str, apelidos: list[str] = (),
                     area_m2: float | None = None, volume_m3: float | None = None) -> Tanque:
    tanque = Tanque(fazenda=fazenda, codigo=codigo, area_m2=area_m2, volume_m3=volume_m3)
    sessao.add(tanque)
    sessao.flush()
    for apelido in apelidos:
        sessao.add(ApelidoTanque(fazenda_id=fazenda.id, tanque_id=tanque.id, apelido=normalizar(apelido)))
    return tanque


def povoar(sessao: Session, tanque: Tanque, especie: str, fase: str, quantidade: int,
           peso_medio_g: float) -> Lote:
    lote = Lote(fazenda_id=tanque.fazenda_id, tanque=tanque, especie=especie, fase=fase,
                quantidade_inicial=quantidade, quantidade_atual=quantidade, peso_medio_g=peso_medio_g)
    sessao.add(lote)
    return lote


def autorizar(sessao: Session, fazenda: Fazenda, telefone: str, nome: str = "",
              consentiu: bool = False) -> Usuario:
    usuario = Usuario(fazenda_id=fazenda.id, telefone=telefone, nome=nome,
                      consentiu_em=agora_utc() if consentiu else None)
    sessao.add(usuario)
    return usuario


TELEFONE_DEMO = "5584999990000"


def criar_fazenda_demo(sessao: Session, telefone: str = TELEFONE_DEMO, consentiu: bool = True) -> Fazenda:
    """Fazenda de exemplo. Biomassas: T1 200 kg, T2 750 kg, T3 50 kg."""
    fazenda = criar_fazenda(sessao, "Fazenda Demonstração", peso_saco_kg=25.0)
    t1 = adicionar_tanque(sessao, fazenda, "T1", ["tanque da entrada"], area_m2=400)
    t2 = adicionar_tanque(sessao, fazenda, "T2", ["tanque do meio"], area_m2=1000)
    t3 = adicionar_tanque(sessao, fazenda, "T3", ["tanque do fundo"], area_m2=300)
    povoar(sessao, t1, "tilapia", "juvenil", 2000, 100)
    povoar(sessao, t2, "tilapia", "engorda", 1500, 500)
    povoar(sessao, t3, "tambaqui", "alevinagem", 5000, 10)
    autorizar(sessao, fazenda, telefone, "Produtor Demo", consentiu=consentiu)
    sessao.flush()
    return fazenda
