"""Testes da guiagem de pouso (pouso.py), sem o KSP.

Uma nave simulada cai na vertical e a mesma Guiagem do script decide o
acelerador. A simulação é mais malvada que o jogo onde dá: gravidade do chão o
caminho todo, arrasto que passa do dobro perto de Mach 1, empuxo que cai no ar
grosso e a guiagem sempre uma volta atrasada (as leituras do kRPC chegam com
atraso, principalmente pelo Wi-Fi).

Uso:
    python test_pouso.py
    python test_pouso.py -v          # uma linha por cenário
"""

import math
import unittest
from dataclasses import dataclass
from unittest import mock

import pouso
from pouso import POUSADA, QUEDA, QUEIMA, V_TOQUE, Guiagem, Leitura, mira

G0 = 9.80665          # m/s²: a do Isp
VEL_SOM = 330.0       # m/s
PASSO_FISICA = 0.02   # s: a física do KSP roda a 50 Hz
ALTURA_CM = 3.0       # m: do pé até o centro de massa
TOQUE_MAX = V_TOQUE + 1.0  # m/s: acima disso o teste falha (as pernas do KSP aguentam bem mais)


@dataclass
class Corpo:
    nome: str
    g: float
    densidade_mar: float = 0.0  # kg/m³
    escala: float = 1.0         # m: altura em que a densidade cai para 1/e
    topo: float = 0.0           # m: fim da atmosfera

    def densidade(self, altitude):
        if altitude >= self.topo:
            return 0.0
        return self.densidade_mar * math.exp(-max(altitude, 0.0) / self.escala)


KERBIN = Corpo("Kerbin", 9.81, 1.225, 5_600, 70_000)
EVE = Corpo("Eve", 16.7, 6.0, 7_200, 90_000)
DUNA = Corpo("Duna", 2.94, 0.03, 5_500, 50_000)
LAYTHE = Corpo("Laythe", 7.85, 0.76, 4_500, 50_000)
MUN = Corpo("Mun", 1.63)
MINMUS = Corpo("Minmus", 0.491)
TYLO = Corpo("Tylo", 7.85)


def fator_mach(velocidade):
    """Quanto o arrasto cresce com a velocidade do som (parecido com o do KSP, só que pior)."""
    pontos = [(0.0, 1.0), (0.8, 1.0), (1.1, 2.2), (2.0, 1.6), (5.0, 1.4)]
    mach = abs(velocidade) / VEL_SOM
    for (m0, f0), (m1, f1) in zip(pontos, pontos[1:]):
        if mach <= m1:
            return f0 + (f1 - f0) * (mach - m0) / (m1 - m0)
    return pontos[-1][1]


class NaveSimulada:
    def __init__(self, corpo, altura, velocidade, twr=2.0, terreno=0.0, massa=10_000.0,
                 area=2.0, isp=300.0, perda=0.15):
        self.corpo = corpo
        self.altura = altura          # m do pé até o chão
        self.v = velocidade           # m/s, para cima
        self.terreno = terreno        # m acima do nível do mar
        self.massa = massa
        self.area = area              # m²: arrasto = área · fator_mach · densidade · v²
        self.isp = isp
        self.perda = perda            # empuxo perdido por atmosfera de pressão (1,225 kg/m³)
        self.empuxo_vacuo = 1.0
        self.empuxo_vacuo = twr * massa * corpo.g / self.empuxo(terreno)

    def empuxo(self, altitude):
        pressao = self.corpo.densidade(altitude) / 1.225
        return self.empuxo_vacuo * max(0.2, 1 - self.perda * pressao)

    def arrasto(self):
        altitude = self.terreno + self.altura + ALTURA_CM
        return self.area * fator_mach(self.v) * self.corpo.densidade(altitude) * self.v**2

    def leitura(self):
        altitude = self.terreno + self.altura + ALTURA_CM
        return Leitura(
            altura=self.altura,
            altitude=altitude,
            velocidade=(self.v, 0.0, 0.0),
            massa=self.massa,
            empuxo=self.empuxo(altitude),
            empuxo_chao=self.empuxo(self.terreno),
            arrasto=self.arrasto(),
            cima=1.0,
            g=self.corpo.g,
            pousada=self.altura <= 0,
        )

    def avancar(self, acelerador, dt):
        empuxo = acelerador * self.empuxo(self.terreno + self.altura + ALTURA_CM)
        arrasto = -math.copysign(self.arrasto(), self.v)
        self.v += ((empuxo + arrasto) / self.massa - self.corpo.g) * dt
        self.altura += self.v * dt
        self.massa -= empuxo / (self.isp * G0) * dt


@dataclass
class Resultado:
    toque: float       # m/s de descida no toque
    ignicao: float     # m: altura em que o motor acendeu pela primeira vez
    combustivel: float  # kg
    tempo: float       # s


def simular(nave, atraso=1, tempo_max=900.0):
    """Roda a guiagem na nave simulada até tocar o chão.

    atraso: quantas voltas do laço a leitura chega atrasada.
    """
    guiagem = Guiagem(nave.corpo.densidade)
    massa_inicial = nave.massa
    fila = []
    acelerador = 0.0
    ignicao = None
    t = 0.0
    proxima_volta = 0.0
    while t < tempo_max:
        if t >= proxima_volta:
            fila.append(nave.leitura())
            if len(fila) > atraso:
                acelerador, _ = guiagem.passo(fila.pop(0))
                if guiagem.fase == QUEIMA and ignicao is None:
                    ignicao = nave.altura
            proxima_volta += pouso.INTERVALO
        nave.avancar(acelerador, PASSO_FISICA)
        t += PASSO_FISICA
        if nave.altura <= 0:
            return Resultado(-nave.v, ignicao, massa_inicial - nave.massa, t)
    raise AssertionError(f"não pousou em {tempo_max:.0f} s (altura {nave.altura:.0f} m)")


# (corpo, altura inicial em m, velocidade inicial em m/s, parâmetros da nave)
CENARIOS = [
    (MUN, 5_000, -100, {}),
    (MUN, 20_000, -300, {"twr": 3.0}),
    (MUN, 1_500, 0, {}),
    (MINMUS, 3_000, -50, {}),
    (TYLO, 10_000, -300, {}),
    (KERBIN, 10_000, -250, {}),
    (KERBIN, 30_000, -900, {"twr": 2.5}),          # booster voltando rápido, passa por Mach 1
    (KERBIN, 3_000, -200, {"twr": 1.4}),           # motor fraco
    (KERBIN, 2_000, 0, {"terreno": 1_500}),        # parada, em cima de um morro
    (KERBIN, 100, 30, {}),                         # salto: começa subindo
    (KERBIN, 10_000, -250, {"perda": 0.5}),        # motor de vácuo, perde muito empuxo no ar
    (DUNA, 8_000, -200, {"twr": 3.0}),
    (EVE, 5_000, -100, {"perda": 0.05}),
    (LAYTHE, 6_000, -200, {}),
]


class TestPouso(unittest.TestCase):
    def test_pousa_em_todos_os_cenarios(self):
        for corpo, altura, velocidade, extras in CENARIOS:
            for atraso in (1, 3):  # 0,05 s (cabo) e 0,15 s (Wi-Fi ruim)
                with self.subTest(corpo=corpo.nome, altura=altura, v=velocidade, atraso=atraso, **extras):
                    r = simular(NaveSimulada(corpo, altura, velocidade, **extras), atraso)
                    self.assertLessEqual(r.toque, TOQUE_MAX)
                    self.assertGreater(r.toque, 0.0)

    def test_arrasto_deixa_acender_mais_tarde(self):
        """Contando o arrasto, a ignição fica mais perto do chão e gasta menos."""
        com = simular(NaveSimulada(KERBIN, 10_000, -250))
        with mock.patch.object(pouso, "FATOR_ARRASTO", 0.0):
            sem = simular(NaveSimulada(KERBIN, 10_000, -250))
        self.assertLess(com.ignicao, sem.ignicao)
        self.assertLess(com.combustivel, sem.combustivel)

    def test_previsao_no_vacuo_bate_com_a_conta(self):
        """Sem ar, a freada tem conta fechada: a = (v² - V_TOQUE²) / (2·d) + g."""
        guiagem = Guiagem(MUN.densidade)
        nave = NaveSimulada(MUN, 4_000, -200, twr=5.0)
        leitura = nave.leitura()
        guiagem.passo(leitura)
        distancia = leitura.altura - pouso.ALTURA_FOLGA
        esperada = (200**2 - V_TOQUE**2) / (2 * distancia) + MUN.g
        self.assertAlmostEqual(guiagem.necessaria, esperada, delta=esperada * 1e-3)

    def test_sem_empuxo_para_parar(self):
        nave = NaveSimulada(MUN, 300, -300)
        guiagem = Guiagem(MUN.densidade)
        acelerador, _ = guiagem.passo(nave.leitura())
        self.assertTrue(math.isinf(guiagem.necessaria))
        self.assertEqual(guiagem.fase, QUEIMA)
        self.assertEqual(acelerador, 1.0)

    def test_sem_motor_ativo(self):
        nave = NaveSimulada(MUN, 1_000, -50)
        leitura = nave.leitura()
        leitura.empuxo = leitura.empuxo_chao = 0.0
        guiagem = Guiagem(MUN.densidade)
        acelerador, _ = guiagem.passo(leitura)
        self.assertEqual(acelerador, 0.0)
        self.assertEqual(guiagem.fase, QUEDA)  # não finge que acendeu

    def test_cai_sem_motor_enquanto_da(self):
        nave = NaveSimulada(MUN, 20_000, -50)
        guiagem = Guiagem(MUN.densidade)
        acelerador, _ = guiagem.passo(nave.leitura())
        self.assertEqual(guiagem.fase, QUEDA)
        self.assertEqual(acelerador, 0.0)

    def test_pousada(self):
        nave = NaveSimulada(MUN, 0, 0)
        guiagem = Guiagem(MUN.densidade)
        acelerador, _ = guiagem.passo(nave.leitura())
        self.assertEqual(guiagem.fase, POUSADA)
        self.assertEqual(acelerador, 0.0)

    def test_mira(self):
        # Parada: em pé.
        self.assertEqual(mira((0.0, 0.0, 0.0), 500.0), (1.0, 0.0, 0.0))
        # Caindo e derivando para o norte: nariz inclinado para o sul.
        cima, norte, leste = mira((-100.0, 10.0, 0.0), 500.0)
        self.assertGreater(cima, 0.99)
        self.assertLess(norte, 0.0)
        # Deriva grande lá em cima: no máximo INCLINACAO_MAX fora da vertical.
        cima, norte, leste = mira((-10.0, 0.0, 50.0), 500.0)
        self.assertAlmostEqual(math.degrees(math.acos(cima)), pouso.INCLINACAO_MAX)
        # Subindo: continua apontando para cima, nunca para baixo.
        self.assertGreater(mira((30.0, 0.0, 0.0), 500.0)[0], 0.99)

    def test_mira_em_pe_perto_do_chao(self):
        """Perto do chão a nave fica em pé, mesmo derivando para o lado."""
        for altura in (0.0, 5.0, pouso.ALTURA_TOQUE):
            cima, _, _ = mira((-2.0, 3.0, 0.0), altura)
            self.assertAlmostEqual(math.degrees(math.acos(cima)), pouso.INCLINACAO_TOQUE)
        # O limite cresce aos poucos com a altura, sem saltos.
        anterior = pouso.inclinacao_permitida(0.0)
        for altura in range(0, 200, 5):
            limite = pouso.inclinacao_permitida(altura)
            self.assertGreaterEqual(limite, anterior)
            self.assertLessEqual(limite - anterior, 1.0)
            anterior = limite


if __name__ == "__main__":
    unittest.main()
