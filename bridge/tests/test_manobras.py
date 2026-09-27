"""Testes do editor de nós de manobra (manobras.py), sem o KSP.

As contas de órbita são conferidas contra uma integração numérica, e o editor
roda contra um kRPC de mentira: órbitas de Kepler em 3D, nós que aplicam a
queima no quadro do nó como o jogo faz, e uma câmera que só guarda valores.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_manobras.py
    python bridge/tests/test_manobras.py -v
"""

import json
import math
import os
import sys
import unittest

# A ponte fica na pasta de cima (bridge/).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from manobras import (
    Editor, angulo_de_voo, duracao_queima, falta_para_circular, para_o_no,
    tempo_ate_anomalia,
)

MU = 3.5316e12          # Kerbin
RAIO = 600_000.0


# ---- vetores ----

def soma(*vs):
    return tuple(sum(c) for c in zip(*vs))


def vezes(k, v):
    return tuple(k * c for c in v)


def escalar(a, b):
    return sum(x * y for x, y in zip(a, b))


def vetorial(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def modulo(v):
    return math.sqrt(escalar(v, v))


def unitario(v):
    return vezes(1 / modulo(v), v)


# ---- o kRPC de mentira ----

class Corpo:
    name = "Kerbin"
    gravitational_parameter = MU
    equatorial_radius = RAIO
    has_atmosphere = True
    atmosphere_depth = 70_000.0


class Orbita:
    """Órbita de Kepler a partir de posição e velocidade num instante."""

    def __init__(self, r0, v0, t0, corpo=None):
        self.body = corpo or Corpo()
        mu = self.body.gravitational_parameter
        self._mu = mu
        h = vetorial(r0, v0)
        self._h = unitario(h)
        v2 = escalar(v0, v0)
        r = modulo(r0)
        e_vec = vezes(1 / mu, soma(vezes(v2 - mu / r, r0), vezes(-escalar(r0, v0), v0)))
        self.eccentricity = modulo(e_vec)
        self.semi_major_axis = 1 / (2 / r - v2 / mu)
        self._p = escalar(h, h) / mu
        self._P = unitario(e_vec) if self.eccentricity > 1e-12 else unitario(r0)
        self._Q = vetorial(self._h, self._P)
        nu0 = math.atan2(escalar(r0, self._Q), escalar(r0, self._P))
        self._t0 = t0
        self._m0 = self._media(nu0)
        self.inclination = math.acos(max(-1.0, min(1.0, self._h[2])))
        self.time_to_soi_change = math.nan
        self.next_orbit = None

    def _n(self):
        return math.sqrt(self._mu / abs(self.semi_major_axis) ** 3)

    def _media(self, nu):
        e = self.eccentricity
        if e < 1:
            E = 2 * math.atan2(math.sqrt(1 - e) * math.sin(nu / 2), math.sqrt(1 + e) * math.cos(nu / 2))
            return E - e * math.sin(E)
        F = 2 * math.atanh(math.sqrt((e - 1) / (e + 1)) * math.tan(nu / 2))
        return e * math.sinh(F) - F

    def true_anomaly_at_ut(self, t):
        e = self.eccentricity
        M = self._m0 + self._n() * (t - self._t0)
        if e < 1:
            M = math.remainder(M, 2 * math.pi)
            E = M if e < 0.8 else math.pi * (1 if M >= 0 else -1)
            for _ in range(50):
                E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
            return math.atan2(math.sqrt(1 - e * e) * math.sin(E), math.cos(E) - e) % (2 * math.pi)
        F = math.asinh(M / e)
        for _ in range(50):
            F -= (e * math.sinh(F) - F - M) / (e * math.cosh(F) - 1)
        return 2 * math.atan(math.sqrt((e + 1) / (e - 1)) * math.tanh(F / 2))

    def estado(self, t):
        nu = self.true_anomaly_at_ut(t)
        e = self.eccentricity
        r = self._p / (1 + e * math.cos(nu))
        pos = soma(vezes(r * math.cos(nu), self._P), vezes(r * math.sin(nu), self._Q))
        k = math.sqrt(self._mu / self._p)
        vel = soma(vezes(-k * math.sin(nu), self._P), vezes(k * (e + math.cos(nu)), self._Q))
        return pos, vel

    def radius_at(self, t):
        return modulo(self.estado(t)[0])

    @property
    def apoapsis(self):
        return self.semi_major_axis * (1 + self.eccentricity)

    @property
    def periapsis(self):
        return self.semi_major_axis * (1 - self.eccentricity)

    @property
    def apoapsis_altitude(self):
        return self.apoapsis - self.body.equatorial_radius

    @property
    def periapsis_altitude(self):
        return self.periapsis - self.body.equatorial_radius

    @property
    def period(self):
        if self.eccentricity >= 1:
            return math.nan
        return 2 * math.pi / self._n()


class No:
    def __init__(self, controle, ut, prograde=0.0, normal=0.0, radial=0.0):
        self._controle = controle
        self.ut, self.prograde, self.normal, self.radial = ut, prograde, normal, radial

    @property
    def orbit(self):
        antes = self._controle.orbita_antes(self)
        r, v = antes.estado(self.ut)
        pro = unitario(v)
        nrm = unitario(vetorial(r, v))
        rad = vetorial(pro, nrm)   # perpendicular ao pró-grado, para fora
        dv = soma(vezes(self.prograde, pro), vezes(self.normal, nrm), vezes(self.radial, rad))
        return Orbita(r, soma(v, dv), self.ut, antes.body)

    @property
    def delta_v(self):
        return math.sqrt(self.prograde ** 2 + self.normal ** 2 + self.radial ** 2)

    remaining_delta_v = delta_v

    def remove(self):
        self._controle.lista.remove(self)


class Controle:
    def __init__(self, nave):
        self._nave = nave
        self.lista = []

    @property
    def nodes(self):
        return sorted(self.lista, key=lambda n: n.ut)

    def add_node(self, ut, prograde=0.0, normal=0.0, radial=0.0):
        no = No(self, ut, prograde, normal, radial)
        self.lista.append(no)
        return no

    def orbita_antes(self, no):
        nos = self.nodes
        i = nos.index(no)
        return nos[i - 1].orbit if i > 0 else self._nave.orbit


class Nave:
    available_thrust = 60_000.0     # N
    specific_impulse = 345.0        # s
    mass = 5_000.0                  # kg

    def __init__(self, orbita):
        self.orbit = orbita
        self.control = Controle(self)


class ModoCamera:
    automatic = "automatic"
    map = "map"


class Camera:
    mode = ModoCamera.automatic
    heading, pitch, distance = 0.0, 10.0, 1e6
    min_pitch, max_pitch = -90.0, 90.0
    min_distance, max_distance = 1e3, 1e10
    focussed_vessel = focussed_node = focussed_body = None


class CentroEspacial:
    CameraMode = ModoCamera

    def __init__(self, orbita):
        self.ut = 0.0
        self.active_vessel = Nave(orbita)
        self.camera = Camera()


class Conexao:
    def __init__(self, orbita):
        self.space_center = CentroEspacial(orbita)


def orbita_eliptica(pe=80_000.0, ap=300_000.0, inclinacao=0.1):
    """Órbita de Kerbin começando no periastro, em t = 0."""
    rp, ra = RAIO + pe, RAIO + ap
    a = (rp + ra) / 2
    vp = math.sqrt(MU * (2 / rp - 1 / a))
    v = (0.0, vp * math.cos(inclinacao), vp * math.sin(inclinacao))
    return Orbita((rp, 0.0, 0.0), v, 0.0)


# ---- testes das contas ----

def integrar(r, v, dt, passos=20000):
    """RK4 do problema de dois corpos: a referência independente de Kepler."""
    def acel(p):
        d = modulo(p)
        return vezes(-MU / d ** 3, p)

    h = dt / passos
    for _ in range(passos):
        k1r, k1v = v, acel(r)
        k2r, k2v = soma(v, vezes(h / 2, k1v)), acel(soma(r, vezes(h / 2, k1r)))
        k3r, k3v = soma(v, vezes(h / 2, k2v)), acel(soma(r, vezes(h / 2, k2r)))
        k4r, k4v = soma(v, vezes(h, k3v)), acel(soma(r, vezes(h, k3r)))
        r = soma(r, vezes(h / 6, soma(k1r, vezes(2, k2r), vezes(2, k3r), k4r)))
        v = soma(v, vezes(h / 6, soma(k1v, vezes(2, k2v), vezes(2, k3v), k4v)))
    return r, v


class TestContas(unittest.TestCase):
    def test_circularizar_em_qualquer_ponto(self):
        """A queima calculada deixa a órbita circular, em elipses e hipérboles."""
        casos = [(0.3, 1.0e6, 0.0), (0.3, 1.0e6, 1.2), (0.3, 1.0e6, math.pi), (0.3, 1.0e6, 4.0),
                 (0.9, 5.0e6, 2.5), (1.5, -1.0e6, 0.6), (0.0, 7.0e5, 1.0)]
        for e, a, nu in casos:
            with self.subTest(e=e, nu=nu):
                p = a * (1 - e * e)
                r = p / (1 + e * math.cos(nu))
                pos = (r * math.cos(nu), r * math.sin(nu), 0.0)
                k = math.sqrt(MU / p)
                vel = (-k * math.sin(nu), k * (e + math.cos(nu)), 0.0)
                gama = angulo_de_voo(e, nu)
                pro, rad = para_o_no(*falta_para_circular(MU, r, a, e, nu), gama)
                # Aplica no quadro do nó, como o jogo.
                u_pro = unitario(vel)
                u_rad = vetorial(u_pro, unitario(vetorial(pos, vel)))
                depois = Orbita(pos, soma(vel, vezes(pro, u_pro), vezes(rad, u_rad)), 0.0)
                self.assertLess(depois.eccentricity, 1e-9)
                self.assertAlmostEqual(depois.semi_major_axis / r, 1.0, places=9)

    def test_tempo_ate_anomalia_contra_integracao(self):
        casos = [(0.2, 9.0e5, 0.3, 2.0), (0.2, 9.0e5, 5.0, 1.0), (1.4, -8.0e5, -1.0, 0.5)]
        for e, a, de, para in casos:
            with self.subTest(e=e, de=de, para=para):
                dt = tempo_ate_anomalia(MU, a, e, de, para)
                p = a * (1 - e * e)
                r = p / (1 + e * math.cos(de))
                pos = (r * math.cos(de), r * math.sin(de), 0.0)
                k = math.sqrt(MU / p)
                vel = (-k * math.sin(de), k * (e + math.cos(de)), 0.0)
                pos, _ = integrar(pos, vel, dt)
                chegou = math.atan2(pos[1], pos[0])
                self.assertAlmostEqual(math.remainder(chegou - para, 2 * math.pi), 0.0, places=5)

    def test_tempo_ate_anomalia_meio_periodo_e_hiperbole(self):
        a = 1.0e6
        periodo = 2 * math.pi * math.sqrt(a ** 3 / MU)
        self.assertAlmostEqual(tempo_ate_anomalia(MU, a, 0.4, 0.0, math.pi), periodo / 2, places=6)
        self.assertAlmostEqual(tempo_ate_anomalia(MU, a, 0.4, math.pi, 0.0), periodo / 2, places=6)
        self.assertIsNone(tempo_ate_anomalia(MU, -1e6, 1.5, 0.5, 0.0))       # o periastro já passou
        self.assertIsNone(tempo_ate_anomalia(MU, -1e6, 1.5, -0.5, math.pi))  # hipérbole não tem apoastro

    def test_duracao_queima(self):
        # Queima pequena: quase massa x Δv / empuxo.
        self.assertAlmostEqual(duracao_queima(0.1, 60_000, 345, 5_000), 5_000 * 0.1 / 60_000, places=5)
        # Queima grande: a nave fica leve, então leva menos que a conta linear.
        self.assertLess(duracao_queima(1000, 60_000, 345, 5_000), 5_000 * 1000 / 60_000)
        self.assertIsNone(duracao_queima(100, 0, 345, 5_000))


# ---- testes do editor ----

class TestEditor(unittest.TestCase):
    def setUp(self):
        self.conn = Conexao(orbita_eliptica())
        self.sc = self.conn.space_center
        self.nave = self.sc.active_vessel
        self.editor = Editor(self.conn)

    def nos(self):
        return self.nave.control.nodes

    def test_novo_no_apoastro(self):
        self.editor.comando("BTN NOVO 1")
        (no,) = self.nos()
        self.assertAlmostEqual(self.nave.orbit.radius_at(no.ut), self.nave.orbit.apoapsis, delta=1.0)
        self.assertAlmostEqual(no.ut, self.nave.orbit.period / 2, delta=0.01)

    def test_circ_no_apoastro(self):
        self.editor.comando("BTN CIRC 1")           # sem nó: cria no apoastro e circulariza
        (no,) = self.nos()
        o = self.nave.orbit
        esperado = math.sqrt(MU / o.apoapsis) - math.sqrt(MU * (2 / o.apoapsis - 1 / o.semi_major_axis))
        self.assertAlmostEqual(no.prograde, esperado, places=3)
        self.assertAlmostEqual(no.radial, 0.0, places=3)
        self.assertLess(no.orbit.eccentricity, 1e-6)

    def test_circ_fora_do_apoastro_zera_o_normal(self):
        self.editor.comando("BTN NOVO 1")
        self.editor.comando("BTN PASSO 1")          # passo de 10 m/s e 1 min
        self.editor.comando("INC TEMPO -7")
        self.editor.comando("INC NRM 2")
        self.editor.comando("BTN CIRC 1")
        (no,) = self.nos()
        self.assertEqual(no.normal, 0.0)
        self.assertNotAlmostEqual(no.radial, 0.0, places=1)
        self.assertLess(no.orbit.eccentricity, 1e-6)

    def test_ajustes_e_passo(self):
        self.editor.comando("BTN NOVO 1")
        (no,) = self.nos()
        self.editor.comando("INC PRO 3")            # passo inicial: 1 m/s
        ut = no.ut
        self.editor.comando("INC TEMPO 2")          # e 10 s
        self.assertAlmostEqual(no.ut, ut + 20)
        self.editor.comando("BTN PASSO 1")          # um passo só: 10 m/s e 1 min
        self.editor.comando("INC PRO -1")
        self.assertAlmostEqual(no.prograde, -7.0)
        self.editor.comando("INC TEMPO 1")
        self.assertAlmostEqual(no.ut, ut + 80)
        self.editor.comando("BTN PASSO 1")          # 100 m/s
        self.editor.comando("BTN PASSO 1")          # volta para 0.1 m/s
        self.editor.comando("INC RAD 5")
        self.assertAlmostEqual(no.radial, 0.5)
        self.editor.comando("INC TEMPO -100000")    # não vai para o passado
        self.assertGreater(no.ut, self.sc.ut)
        self.assertEqual(self.editor.estado()["passos"], {"PRO": "0.1 m/s", "NRM": "0.1 m/s", "RAD": "0.1 m/s", "TEMPO": "1 s"})

    def test_varios_nos(self):
        self.editor.comando("BTN CIRC 1")
        self.editor.comando("BTN NOVO 1")           # depois do primeiro
        primeiro, segundo = self.nos()
        self.assertGreater(segundo.ut, primeiro.ut)
        self.editor.comando("INC PRO 5")            # mexe no escolhido: o novo
        self.assertEqual(segundo.prograde, 5.0)
        antes = primeiro.prograde
        self.editor.comando("BTN ANT 1")
        self.editor.comando("INC PRO 1")
        self.assertAlmostEqual(primeiro.prograde, antes + 1)
        self.editor.comando("BTN PROX 1")
        self.editor.comando("BTN PROX 1")           # dá a volta: de novo o primeiro
        self.editor.comando("BTN APAGAR 1")
        self.assertEqual(self.nos(), [segundo])
        self.editor.comando("BTN APAGAR 1")
        self.assertEqual(self.nos(), [])
        self.editor.comando("BTN APAGAR 1")         # sem nó: só avisa
        self.assertIn("NOVO", self.editor.estado()["aviso"])

    def test_estado_vira_json(self):
        json.dumps(self.editor.estado())
        self.editor.comando("BTN CIRC 1")
        self.editor.comando("BTN MAPA 1")
        self.editor.comando("BTN CAM_FOCO 1")
        estado = self.editor.estado()
        texto = json.dumps(estado)
        self.assertTrue(texto.isascii())
        titulos = [s["titulo"] for s in estado["secoes"]]
        self.assertIn("NO DE MANOBRA", titulos)
        self.assertIn("ORBITA", titulos)

    def test_camera_do_mapa(self):
        cam = self.sc.camera
        self.editor.comando("BTN CAM_DIR 1")        # fora do mapa: não mexe
        self.assertEqual(cam.heading, 0.0)
        self.editor.comando("BTN MAPA 1")
        self.assertEqual(cam.mode, "map")
        self.editor.comando("BTN CAM_DIR 1")
        self.editor.comando("BTN CAM_PERTO 1")
        self.assertEqual(cam.heading, 15.0)
        self.assertLess(cam.distance, 1e6)
        self.editor.comando("BTN MAPA 1")
        self.assertEqual(cam.mode, "automatic")

    def test_linha_errada(self):
        self.editor.comando("INC PRO x")
        self.assertEqual(self.editor.estado()["aviso"], "ERR INC PRO x")
        self.editor.comando("BTN AP 1")             # AP e PE saíram: o TEMPO leva o nó
        self.assertEqual(self.editor.estado()["aviso"], "ERR BTN AP")
        self.editor.comando("BTN NOVO 0")           # soltar não faz nada
        self.assertEqual(self.nos(), [])


if __name__ == "__main__":
    unittest.main()
