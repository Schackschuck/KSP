"""Testes do fly by wire (fbw.py), sem o KSP.

Um avião simulado voa com a mesma FlyByWire do script decidindo as
superfícies. A simulação tenta ser um pouco pior que o jogo: as superfícies
levam um tempo para mexer, o FBW recebe cada leitura uma volta atrasada (as
leituras do kRPC chegam com atraso, principalmente pelo Wi-Fi), e o avião é
estável como os do KSP: com o profundor no centro, o nariz volta sozinho para
um ângulo de ataque, o de voar nivelado na velocidade do começo.

Uso, a partir da raiz do repositório:
    python scripts/tests/test_fbw.py
    python scripts/tests/test_fbw.py -v    # uma linha por cenário
"""

import math
import os
import sys
import unittest
from dataclasses import dataclass, field

# Os scripts ficam na pasta de cima (scripts/).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fbw
from fbw import (
    ALFA_MAX, DIRETA, FBW, GAMA_MAX, INCLINACAO_MAX, LADO_MAX, FlyByWire, Leitura, Manche,
    angulo180, base_da_nave, curva, direcao, escalar, modulo,
)

G = 9.81
PASSO_FISICA = 0.02    # s: a física do KSP roda a 50 Hz
PASSO_FBW = 0.04       # s: o FBW decide 25 vezes por segundo
Q_REF = 10_000.0       # Pa: pressão dinâmica em que as constantes de giro abaixo valem
V_REF = math.sqrt(2 * Q_REF / 1.225)  # m/s: a velocidade com Q_REF ao nível do mar


def soma(*vetores):
    return tuple(sum(c) for c in zip(*vetores))


def vezes(k, v):
    return tuple(k * c for c in v)


def unitario(v):
    return vezes(1.0 / modulo(v), v)


def angulos_da_base(frente, direita):
    """O contrário de fbw.base_da_nave: (pitch, rumo, rolagem) em graus."""
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, frente[0]))))
    rumo = math.degrees(math.atan2(frente[2], frente[1])) % 360.0
    p, r = math.radians(pitch), math.radians(rumo)
    direita0 = (0.0, -math.sin(r), math.cos(r))
    cima0 = (math.cos(p), -math.sin(p) * math.cos(r), -math.sin(p) * math.sin(r))
    rolagem = math.degrees(math.atan2(-escalar(direita, cima0), escalar(direita, direita0)))
    return pitch, rumo, rolagem


@dataclass
class Aviao:
    """Um avião de uns 6 t, parecido com os pequenos do KSP.

    As acelerações angulares estão em rad/s² com o comando todo, na pressão
    dinâmica Q_REF; elas crescem junto com a pressão. As rodas de reação da
    cabine somam RODA, que não depende do ar.
    """
    massa: float = 6000.0
    area: float = 15.0            # m²
    cl_alfa: float = 5.0          # sustentação por radiano de ângulo de ataque
    alfa_estol: float = 22.0      # graus: acima disso a sustentação cai
    cd0: float = 0.02
    k_induzido: float = 0.1
    cy_beta: float = 1.0          # força de lado por radiano de escorregamento
    empuxo_max: float = 40_000.0  # N
    # pitch: profundor, estabilidade (o nariz volta para alfa_trim) e amortecimento
    alfa_trim: float = None       # graus de ataque com o profundor no centro; None = o de voar nivelado
    profundor: float = 3.0
    estabilidade: float = 15.0
    amortecimento_pitch: float = 3.0
    # roll: aileron e amortecimento
    aileron: float = 6.0
    amortecimento_roll: float = 4.0
    # yaw: leme, cata-vento (o nariz vira para o lado do movimento) e amortecimento
    leme: float = 2.0
    cata_vento: float = 8.0
    amortecimento_yaw: float = 2.0
    roda: float = 0.3
    tau_superficie: float = 0.1   # s: as superfícies não mexem na hora
    # quanto a autoridade informada ao FBW erra (o kRPC pode errar a conta)
    erro_autoridade: float = 1.0

    altitude: float = 2000.0
    velocidade: tuple = (0.0, 0.0, 150.0)   # (cima, norte, leste): para leste
    base: tuple = None                        # (frente, direita, cima)
    giros: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # pitch, roll, yaw em rad/s
    superficies: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    acelerador: float = 0.2
    no_chao: bool = False
    t: float = 0.0

    def __post_init__(self):
        if self.alfa_trim is None:
            self.alfa_trim = self.alfa_equilibrio()
        if self.base is None:
            gama, rumo = direcao(self.velocidade)
            self.base = base_da_nave(gama + self.alfa_equilibrio(), rumo, 0.0)
        self.forca_aero = (0.0, 0.0, 0.0)
        self.maior_alfa = -math.inf

    def densidade(self):
        return 1.225 * math.exp(-max(self.altitude, 0.0) / 5600.0)

    def pressao(self):
        return 0.5 * self.densidade() * escalar(self.velocidade, self.velocidade)

    def alfa_equilibrio(self):
        """Graus de ataque para voar reto e nivelado: começa já equilibrado."""
        return math.degrees(self.massa * G / (self.pressao() * self.area * self.cl_alfa))

    def cl(self, alfa):
        estol = math.radians(self.alfa_estol)
        if abs(alfa) <= estol:
            return self.cl_alfa * alfa
        # Depois do estol, a sustentação cai pela metade em 10°.
        excesso = min(abs(alfa) - estol, math.radians(10.0))
        return math.copysign(self.cl_alfa * estol * (1 - 0.5 * excesso / math.radians(10.0)), alfa)

    def autoridade(self):
        a = self.pressao() / Q_REF
        return tuple(
            self.erro_autoridade * (k * a + self.roda) for k in (self.profundor, self.aileron, self.leme)
        )

    def leitura(self):
        pitch, rumo, rolagem = angulos_da_base(self.base[0], self.base[1])
        return Leitura(
            pitch=pitch,
            rumo=rumo,
            rolagem=rolagem,
            velocidade=self.velocidade,
            altitude=self.altitude,
            pressao=self.pressao(),
            forca_aero=self.forca_aero,
            massa=self.massa,
            g=G,
            autoridade=self.autoridade(),
            no_chao=self.no_chao,
            ut=self.t,
        )

    def passo(self, comandos, dt=PASSO_FISICA):
        frente, direita, cima = self.base
        v = modulo(self.velocidade)
        vu = unitario(self.velocidade)
        q = self.pressao()
        alfa, beta = fbw.angulos_do_ar(self.velocidade, self.base)
        self.maior_alfa = max(self.maior_alfa, math.degrees(alfa))

        # Forças: a sustentação é perpendicular ao movimento, do lado do "cima"
        # da nave; a força de lado empurra contra o escorregamento.
        cl = self.cl(alfa)
        dir_sustentacao = unitario(soma(cima, vezes(-escalar(cima, vu), vu)))
        dir_lado = unitario(soma(direita, vezes(-escalar(direita, vu), vu)))
        sustentacao = vezes(q * self.area * cl, dir_sustentacao)
        lado = vezes(-q * self.area * self.cy_beta * beta, dir_lado)
        arrasto = vezes(-q * self.area * (self.cd0 + self.k_induzido * cl * cl), vu)
        self.forca_aero = soma(sustentacao, lado, arrasto)
        empuxo = vezes(self.empuxo_max * self.acelerador, frente)
        aceleracao = soma(vezes(1.0 / self.massa, soma(self.forca_aero, empuxo)), (-G, 0.0, 0.0))
        self.velocidade = soma(self.velocidade, vezes(dt, aceleracao))
        self.altitude += self.velocidade[0] * dt

        # Superfícies: seguem o comando com atraso.
        pedidos = (comandos.pitch, comandos.roll, comandos.yaw)
        for i, pedido in enumerate(pedidos):
            self.superficies[i] += (pedido - self.superficies[i]) * dt / self.tau_superficie
        if comandos.acelerador is not None:
            self.acelerador = comandos.acelerador

        # As superfícies e a estabilidade crescem com a pressão dinâmica; o
        # amortecimento, com densidade · velocidade (o giro muda o ângulo do
        # ar em cada ponta da asa por giro · envergadura / v).
        a = q / Q_REF
        amortece = a * V_REF / v
        gp, gr, gy = self.giros
        sp, sr, sy = self.superficies
        gp += dt * (a * (self.profundor * sp - self.estabilidade * (alfa - math.radians(self.alfa_trim)))
                    - amortece * self.amortecimento_pitch * gp + self.roda * sp)
        gr += dt * (a * self.aileron * sr - amortece * self.amortecimento_roll * gr + self.roda * sr)
        gy += dt * (a * (self.leme * sy + self.cata_vento * beta) - amortece * self.amortecimento_yaw * gy
                    + self.roda * sy)
        self.giros = [gp, gr, gy]

        # Gira os eixos da nave (ângulos pequenos) e acerta para continuarem
        # perpendiculares: pitch leva o nariz para o "cima", roll abaixa a asa
        # direita e yaw leva o nariz para a direita.
        frente2 = soma(frente, vezes(gp * dt, cima), vezes(gy * dt, direita))
        direita2 = soma(direita, vezes(-gr * dt, cima), vezes(-gy * dt, frente))
        frente2 = unitario(frente2)
        direita2 = unitario(soma(direita2, vezes(-escalar(direita2, frente2), frente2)))
        # cima = frente × direita nestes eixos, feito componente a componente
        cima2 = unitario(soma(cima, vezes(-gp * dt, frente), vezes(gr * dt, direita)))
        cima2 = unitario(soma(cima2, vezes(-escalar(cima2, frente2), frente2), vezes(-escalar(cima2, direita2), direita2)))
        self.base = (frente2, direita2, cima2)
        self.t += dt


def voar(aviao, guiagem, duracao, manche=lambda t: Manche(), a_cada_passo=None):
    """Voa `duracao` segundos. O FBW decide a cada PASSO_FBW com a leitura da volta anterior."""
    passos_por_decisao = round(PASSO_FBW / PASSO_FISICA)
    leitura_atrasada = aviao.leitura()
    comandos = guiagem.passo(leitura_atrasada, manche(aviao.t))
    fim = aviao.t + duracao
    i = 0
    while aviao.t < fim - 1e-9:
        if i % passos_por_decisao == 0:
            comandos = guiagem.passo(leitura_atrasada, manche(aviao.t))
            leitura_atrasada = aviao.leitura()
            if a_cada_passo is not None:
                a_cada_passo(aviao, guiagem)
        aviao.passo(comandos)
        i += 1


def fbw_no_ar(aviao, **kwargs):
    """Um FBW que já assumiu: passa o tempo da decolagem sem mexer no avião."""
    guiagem = FlyByWire()
    for atributo, valor in kwargs.items():
        setattr(guiagem, atributo, valor)
    voar(aviao, guiagem, fbw.TEMPO_DECOLAGEM + 0.2)
    assert guiagem.lei == FBW, guiagem.motivo
    return guiagem


def trajetoria(aviao):
    return direcao(aviao.velocidade)


class Extremos:
    """Guarda a maior inclinação das asas durante o voo."""

    def __init__(self):
        self.inclinacao = 0.0

    def __call__(self, aviao, guiagem):
        _, _, rolagem = angulos_da_base(aviao.base[0], aviao.base[1])
        self.inclinacao = max(self.inclinacao, abs(rolagem))


class TestContas(unittest.TestCase):
    def test_base_e_angulos_se_desfazem(self):
        for pitch, rumo, rolagem in [(0, 0, 0), (10, 90, 30), (-25, 200, -70), (5, 359, 179)]:
            frente, direita, _ = base_da_nave(pitch, rumo, rolagem)
            p, r, o = angulos_da_base(frente, direita)
            self.assertAlmostEqual(p, pitch, places=6)
            self.assertAlmostEqual(angulo180(r - rumo), 0.0, places=6)
            self.assertAlmostEqual(angulo180(o - rolagem), 0.0, places=6)

    def test_rolar_para_a_direita_abaixa_a_asa_direita(self):
        _, direita, cima = base_da_nave(0, 0, 30)
        self.assertLess(direita[0], 0)   # a asa direita aponta para baixo
        self.assertGreater(cima[2], 0)   # o "cima" da nave pende para a direita (leste, voando para o norte)

    def test_curva_do_manche(self):
        self.assertEqual(curva(fbw.ZONA_MORTA * 0.9), 0.0)
        self.assertEqual(curva(1.0), 1.0)
        self.assertEqual(curva(-1.0), -1.0)
        self.assertGreater(curva(0.5), 0.0)
        self.assertLess(curva(0.5), 0.5)          # mais fina perto do centro
        self.assertEqual(curva(-0.5), -curva(0.5))


class TestLeis(unittest.TestCase):
    def test_no_chao_o_manche_vai_direto(self):
        aviao = Aviao(no_chao=True)
        guiagem = FlyByWire()
        c = guiagem.passo(aviao.leitura(), Manche(pitch=0.8, roll=-0.3, yaw=0.5, acelerador=0.7))
        self.assertEqual(guiagem.lei, DIRETA)
        self.assertEqual((c.pitch, c.roll, c.yaw, c.acelerador), (curva(0.8), curva(-0.3), curva(0.5), 0.7))

    def test_assume_depois_de_um_segundo_no_ar_com_o_ponto_no_progrado(self):
        aviao = Aviao()
        guiagem = FlyByWire()
        voar(aviao, guiagem, fbw.TEMPO_DECOLAGEM - 0.2)
        self.assertEqual(guiagem.lei, DIRETA)
        voar(aviao, guiagem, 0.4)
        self.assertEqual(guiagem.lei, FBW)
        gama, rumo = trajetoria(aviao)
        self.assertAlmostEqual(guiagem.ponto[0], 0.0, delta=0.5)
        self.assertAlmostEqual(angulo180(guiagem.ponto[1] - rumo), 0.0, delta=0.5)

    def test_desligado_no_botao_e_lei_direta(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        guiagem.ligado = False
        c = guiagem.passo(aviao.leitura(), Manche(pitch=0.3))
        self.assertEqual(guiagem.lei, DIRETA)
        self.assertIsNone(guiagem.ponto)
        self.assertEqual(c.pitch, curva(0.3))

    def test_ar_ralo_e_lei_direta(self):
        aviao = Aviao(altitude=40_000, velocidade=(0.0, 0.0, 150.0))
        guiagem = FlyByWire()
        voar(aviao, guiagem, 1.5)
        self.assertEqual(guiagem.lei, DIRETA)


class TestPonto(unittest.TestCase):
    def test_manche_para_tras_sobe_o_ponto_e_solto_ele_para(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        voar(aviao, guiagem, 1.0, lambda t: Manche(pitch=1.0))
        self.assertAlmostEqual(guiagem.ponto[0], fbw.VEL_PONTO_PITCH * 1.0, delta=0.5)
        self.assertIsNone(guiagem.altitude_travada)
        antes = guiagem.ponto
        voar(aviao, guiagem, 2.0)
        self.assertAlmostEqual(guiagem.ponto[0], antes[0], places=6)

    def test_o_ponto_nao_passa_dos_limites(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        voar(aviao, guiagem, 10.0, lambda t: Manche(pitch=1.0, roll=1.0))
        self.assertLessEqual(guiagem.ponto[0], GAMA_MAX)
        _, rumo = trajetoria(aviao)
        self.assertLessEqual(abs(angulo180(guiagem.ponto[1] - rumo)), LADO_MAX + 1e-6)

    def test_trava_a_altitude_com_o_manche_solto_perto_do_horizonte(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        self.assertIsNotNone(guiagem.altitude_travada)
        voar(aviao, guiagem, 0.5, lambda t: Manche(pitch=0.5))
        self.assertIsNone(guiagem.altitude_travada)


class TestVoo(unittest.TestCase):
    def assertSeguiuOPonto(self, aviao, guiagem, tolerancia=0.5):
        gama, rumo = trajetoria(aviao)
        gama_c, rumo_c = guiagem.comando
        self.assertAlmostEqual(gama, gama_c, delta=tolerancia)
        self.assertAlmostEqual(angulo180(rumo - rumo_c), 0.0, delta=tolerancia)

    def test_segura_reto_e_nivelado(self):
        for velocidade in (100.0, 150.0, 280.0):
            with self.subTest(velocidade=velocidade):
                aviao = Aviao(velocidade=(0.0, 0.0, velocidade))
                guiagem = fbw_no_ar(aviao, velocidade_alvo=velocidade)
                altitude = guiagem.altitude_travada
                voar(aviao, guiagem, 60.0)
                self.assertAlmostEqual(aviao.altitude, altitude, delta=3.0)
                self.assertSeguiuOPonto(aviao, guiagem)
                _, _, rolagem = angulos_da_base(aviao.base[0], aviao.base[1])
                self.assertAlmostEqual(rolagem, 0.0, delta=1.0)

    def test_curva_de_90_graus(self):
        for velocidade in (100.0, 150.0, 280.0):
            with self.subTest(velocidade=velocidade):
                aviao = Aviao(velocidade=(0.0, 0.0, velocidade))
                guiagem = fbw_no_ar(aviao, velocidade_alvo=velocidade)
                altitude = guiagem.altitude_travada
                extremos = Extremos()
                # Manche para a direita até o ponto andar 90°, e solta.
                duracao = 90.0 / fbw.VEL_PONTO_RUMO
                voar(aviao, guiagem, duracao, lambda t: Manche(roll=1.0), extremos)
                voar(aviao, guiagem, 60.0, a_cada_passo=extremos)
                # Rápido, o avião vira devagar e o ponto fica na beirada (LADO_MAX), sendo levado.
                self.assertGreater(angulo180(guiagem.ponto[1] - 90.0), LADO_MAX)
                self.assertSeguiuOPonto(aviao, guiagem)
                self.assertLessEqual(extremos.inclinacao, INCLINACAO_MAX + 3.0)
                self.assertAlmostEqual(aviao.altitude, altitude, delta=5.0)

    def test_devagar_a_curva_abre_em_vez_de_descer(self):
        # A 100 m/s, 60° de inclinação pediriam mais que ALFA_MAX da asa.
        aviao = Aviao(velocidade=(0.0, 0.0, 100.0))
        guiagem = fbw_no_ar(aviao, velocidade_alvo=100.0)
        altitude = guiagem.altitude_travada
        pior = {"altitude": 0.0}

        def medir(aviao, guiagem):
            pior["altitude"] = max(pior["altitude"], abs(aviao.altitude - altitude))

        extremos = Extremos()
        voar(aviao, guiagem, 90.0 / fbw.VEL_PONTO_RUMO, lambda t: Manche(roll=1.0), extremos)
        voar(aviao, guiagem, 60.0, a_cada_passo=lambda a, g: (extremos(a, g), medir(a, g)))
        self.assertLess(extremos.inclinacao, 50.0)
        self.assertLess(pior["altitude"], 15.0)
        self.assertLessEqual(aviao.maior_alfa, ALFA_MAX + 1.0)
        self.assertSeguiuOPonto(aviao, guiagem)

    def test_sobe_e_nivela(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao, velocidade_alvo=150.0)
        # Manche para trás até o ponto chegar a uns 10°.
        voar(aviao, guiagem, 10.0 / fbw.VEL_PONTO_PITCH, lambda t: Manche(pitch=1.0))
        voar(aviao, guiagem, 20.0)
        self.assertAlmostEqual(guiagem.ponto[0], 10.0, delta=0.5)
        self.assertSeguiuOPonto(aviao, guiagem)
        # Para a frente até o ponto voltar a quase zero: trava a altitude.
        voar(aviao, guiagem, 9.7 / fbw.VEL_PONTO_PITCH, lambda t: Manche(pitch=-1.0))
        voar(aviao, guiagem, 1.0)
        self.assertIsNotNone(guiagem.altitude_travada)
        altitude = guiagem.altitude_travada
        voar(aviao, guiagem, 40.0)
        self.assertAlmostEqual(aviao.altitude, altitude, delta=3.0)

    def test_leme_coordena_a_curva(self):
        # Cauda fraca: sem o leme, o avião escorregaria de lado na curva.
        aviao = Aviao(velocidade=(0.0, 0.0, 100.0), cata_vento=2.0)
        guiagem = fbw_no_ar(aviao, velocidade_alvo=100.0)
        pior = {"beta": 0.0}

        def medir(aviao, guiagem):
            pior["beta"] = max(pior["beta"], abs(guiagem.diagnostico.get("beta", 0.0)))

        voar(aviao, guiagem, 6.0, lambda t: Manche(roll=1.0), medir)
        voar(aviao, guiagem, 30.0, a_cada_passo=medir)
        self.assertLess(pior["beta"], 6.0)

    def test_protecao_do_angulo_de_ataque(self):
        # Profundor forte, que sozinho levaria a asa ao estol, e motor desligado.
        aviao = Aviao(velocidade=(0.0, 0.0, 90.0), profundor=8.0, acelerador=0.0)
        guiagem = fbw_no_ar(aviao)
        aviao.maior_alfa = -math.inf
        voar(aviao, guiagem, 30.0, lambda t: Manche(pitch=1.0))
        self.assertLessEqual(aviao.maior_alfa, ALFA_MAX + 1.5)
        self.assertLess(aviao.maior_alfa, aviao.alfa_estol)

    def test_autoridade_errada(self):
        """O kRPC pode errar o torque disponível: pela metade ou em dobro, ainda voa."""
        for erro in (0.5, 2.0):
            with self.subTest(erro=erro):
                aviao = Aviao(erro_autoridade=erro)
                guiagem = fbw_no_ar(aviao, velocidade_alvo=150.0)
                altitude = guiagem.altitude_travada
                extremos = Extremos()
                voar(aviao, guiagem, 90.0 / fbw.VEL_PONTO_RUMO, lambda t: Manche(roll=-1.0), extremos)
                voar(aviao, guiagem, 60.0, a_cada_passo=extremos)
                self.assertSeguiuOPonto(aviao, guiagem)
                self.assertLessEqual(extremos.inclinacao, INCLINACAO_MAX + 5.0)
                self.assertAlmostEqual(aviao.altitude, altitude, delta=8.0)

    def test_acelerador_automatico(self):
        aviao = Aviao(velocidade=(0.0, 0.0, 120.0))
        guiagem = fbw_no_ar(aviao, velocidade_alvo=180.0)
        voar(aviao, guiagem, 90.0)
        self.assertAlmostEqual(modulo(aviao.velocidade), 180.0, delta=2.0)

    def test_acelerador_na_mao(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        c = guiagem.passo(aviao.leitura(), Manche())
        self.assertIsNone(c.acelerador)       # alavanca parada: não mexe no jogo
        c = guiagem.passo(aviao.leitura(), Manche(acelerador=0.8))
        self.assertEqual(c.acelerador, 0.8)


class TestPilotoAutomatico(unittest.TestCase):
    def test_hdg_vira_para_o_rumo_e_segura(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao, velocidade_alvo=150.0)
        altitude = aviao.altitude
        guiagem.definir("HDG", 180.0)   # de leste para sul: 90° à direita
        self.assertTrue(guiagem.alternar_modo("HDG"))
        voar(aviao, guiagem, 60.0)
        _, rumo = trajetoria(aviao)
        self.assertAlmostEqual(angulo180(rumo - 180.0), 0.0, delta=1.0)
        self.assertEqual(guiagem.estado_ap("HDG"), 1)
        self.assertAlmostEqual(aviao.altitude, altitude, delta=10.0)

    def test_vs_sobe_com_a_velocidade_escolhida(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao, velocidade_alvo=150.0)
        guiagem.definir("VS", 5.0)
        guiagem.alternar_modo("VS")
        self.assertIsNone(guiagem.altitude_travada)
        voar(aviao, guiagem, 30.0)
        self.assertAlmostEqual(aviao.velocidade[0], 5.0, delta=0.5)

    def test_alt_armado_sobe_e_nivela(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao, velocidade_alvo=150.0)
        guiagem.definir("ALT", 2300.0)
        guiagem.alternar_modo("ALT")
        voar(aviao, guiagem, 2.0)
        self.assertEqual(guiagem.estado_ap("ALT"), 2)    # armado: subindo
        voar(aviao, guiagem, 90.0)
        self.assertEqual(guiagem.estado_ap("ALT"), 1)    # chegou e segura
        self.assertAlmostEqual(aviao.altitude, 2300.0, delta=5.0)

    def test_alt_com_vs_nivela_e_o_vs_termina(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao, velocidade_alvo=150.0)
        guiagem.definir("ALT", 1700.0)
        guiagem.definir("VS", -4.0)
        guiagem.alternar_modo("ALT")
        guiagem.alternar_modo("VS")
        voar(aviao, guiagem, 20.0)
        self.assertAlmostEqual(aviao.velocidade[0], -4.0, delta=0.6)
        voar(aviao, guiagem, 90.0)
        self.assertFalse(guiagem.ap["VS"])
        self.assertEqual(guiagem.estado_ap("ALT"), 1)
        self.assertAlmostEqual(aviao.altitude, 1700.0, delta=5.0)

    def test_manche_devolve_o_ponto_ao_piloto(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        guiagem.definir("ALT", 3000.0)   # longe: o ALT fica armado e o V/S continua
        for nome in ("HDG", "ALT", "VS"):
            guiagem.alternar_modo(nome)
        voar(aviao, guiagem, 0.5, lambda t: Manche(roll=0.5))
        self.assertEqual(guiagem.ap, {"HDG": False, "ALT": True, "VS": True})
        voar(aviao, guiagem, 0.5, lambda t: Manche(pitch=0.5))
        self.assertEqual(guiagem.ap, {"HDG": False, "ALT": False, "VS": False})

    def test_so_liga_voando_no_fbw_e_desliga_na_lei_direta(self):
        aviao = Aviao()
        guiagem = FlyByWire()
        self.assertFalse(guiagem.alternar_modo("HDG"))    # ainda na lei direta
        voar(aviao, guiagem, fbw.TEMPO_DECOLAGEM + 0.2)
        self.assertTrue(guiagem.alternar_modo("HDG"))
        guiagem.ligado = False
        voar(aviao, guiagem, 0.1)
        self.assertEqual(guiagem.lei, DIRETA)
        self.assertFalse(guiagem.ap["HDG"])

    def test_korry_da_trava_solta_e_trava(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        self.assertIsNotNone(guiagem.altitude_travada)
        guiagem.alternar_trava()
        voar(aviao, guiagem, 2.0)
        self.assertIsNone(guiagem.altitude_travada)       # não trava sozinho de novo
        guiagem.alternar_trava()
        voar(aviao, guiagem, 0.1)
        self.assertAlmostEqual(guiagem.altitude_travada, aviao.altitude, delta=2.0)


class TestConversaComAPonte(unittest.TestCase):
    def test_linhas_de_estado(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        guiagem.alternar_modo("ALT")
        linhas = fbw.linhas_de_estado(guiagem)
        self.assertTrue(linhas[0].startswith("FBW "))
        self.assertIn("LEI FBW", linhas)
        self.assertIn("TRAVA OFF", linhas)              # o ALT soltou a trava
        self.assertIn("APL ALT 2", linhas)
        self.assertIn("APL HDG 0", linhas)
        self.assertEqual(fbw.linhas_de_estado(None)[:3], ["FBW OFF", "LEI OFF", "TRAVA OFF"])
        self.assertIn("LEI CHAO", fbw.linhas_de_estado(FlyByWire()))
        desligado = FlyByWire()
        desligado.ligado = False
        desligado.passo(Aviao(no_chao=True).leitura(), Manche())
        self.assertIn("LEI CHAO", fbw.linhas_de_estado(desligado))   # desligado, mas no chão
        guiagem.ligado = False
        voar(aviao, guiagem, 0.1)
        self.assertIn("LEI DIRETA", fbw.linhas_de_estado(guiagem))    # no ar: DIRETA acende âmbar
        for linha in linhas:
            self.assertLessEqual(len(linha), 31)

    def test_executa_os_comandos_da_ponte(self):
        aviao = Aviao()
        guiagem = fbw_no_ar(aviao)
        self.assertIsNone(fbw.executar("APV VS -25", guiagem))
        self.assertEqual(guiagem.ap_valores["VS"], -2.5)
        fbw.executar("APV HDG 370", guiagem)
        self.assertEqual(guiagem.ap_valores["HDG"], 10.0)
        fbw.executar("CMD HDG", guiagem)
        self.assertTrue(guiagem.ap["HDG"])
        fbw.executar("CMD FBW", guiagem)
        self.assertFalse(guiagem.ligado)
        self.assertIn("desconhecida", fbw.executar("CMD XYZ", guiagem))
        self.assertIn("desconhecida", fbw.executar("APV ALT abc", guiagem))


if __name__ == "__main__":
    unittest.main()
