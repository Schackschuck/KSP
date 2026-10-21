"""Testes das contas do rendezvous (rendezvous.py), sem o KSP.

Uso, a partir da raiz do repositório:
    python scripts/tests/test_rendezvous.py
    python scripts/tests/test_rendezvous.py -v    # uma linha por teste
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import rendezvous
from rendezvous import (
    D_MIRA,
    FOLGA_AR,
    FOLGA_CHAO,
    Estado,
    Planeta,
    chute_tangencial,
    dv_disponivel,
    interceptar,
    menor_distancia,
    periodo,
    planejar_transferencia,
    propagar,
    w_no,
)
from subida import angulo, cruz, elementos, esc, no_relativo, norma, ponto, rotacionar, soma, sub, unit

KERBIN = Planeta("Kerbin", 3.5316e12, 600_000.0, 70_000.0, 84_159_286.0)
MUN = Planeta("Mun", 6.5138398e10, 200_000.0, 0.0, 2_429_559.1)
MU = KERBIN.mu
POLO = (0.0, 1.0, 0.0)
UT_HOJE = 52_234_731.91853178

HOJE_NAVE = Estado(
    UT_HOJE,
    (-78290.2902049169, -1360.7434381412018, -753771.1251473312),
    (2147.6951065771736, 4.454166654098578, -222.56623357898968),
)
HOJE_ALVO = Estado(
    UT_HOJE,
    (-592222.4199506764, -2165.5136644409645, -473168.18995646987),
    (1368.6752355129909, 0.4863146922667238, -1669.4800787542667),
)


def circular(planeta, altitude, fase_graus, t=UT_HOJE, normal=POLO):
    """Estado circular a altitude m, com a posição girada fase_graus (no sentido do movimento) a partir de x."""
    r0 = rotacionar((1.0, 0.0, 0.0), normal, math.radians(fase_graus))
    raio = planeta.raio + altitude
    return Estado(t, esc(raio, r0), esc(math.sqrt(planeta.mu / raio), unit(cruz(normal, r0))))


def energia(mu, r, v):
    return ponto(v, v) / 2.0 - mu / norma(r)


def hohmann(mu, r1, r2):
    a = (r1 + r2) / 2.0
    dv1 = abs(math.sqrt(mu * (2.0 / r1 - 1.0 / a)) - math.sqrt(mu / r1))
    dv2 = abs(math.sqrt(mu / r2) - math.sqrt(mu * (2.0 / r2 - 1.0 / a)))
    return dv1 + dv2


def aceleracao(mu, r):
    return esc(-mu / norma(r) ** 3, r)


def rk4(mu, r, v, dt, passo):
    """Integra a órbita por Runge-Kutta de 4ª ordem, em passos de `passo` s."""
    n = round(dt / passo)
    h = dt / n
    for _ in range(n):
        k1r, k1v = v, aceleracao(mu, r)
        k2r = soma(v, esc(h / 2, k1v))
        k2v = aceleracao(mu, soma(r, esc(h / 2, k1r)))
        k3r = soma(v, esc(h / 2, k2v))
        k3v = aceleracao(mu, soma(r, esc(h / 2, k2r)))
        k4r = soma(v, esc(h, k3v))
        k4v = aceleracao(mu, soma(r, esc(h, k3r)))
        r = soma(r, esc(h / 6, soma(soma(k1r, esc(2, k2r)), soma(esc(2, k3r), k4r))))
        v = soma(v, esc(h / 6, soma(soma(k1v, esc(2, k2v)), soma(esc(2, k3v), k4v))))
    return r, v


class TestPropagar(unittest.TestCase):
    def test_uma_volta_circular_volta_ao_inicio(self):
        e = circular(KERBIN, 150_000.0, 30.0)
        r, v = propagar(MU, e.r, e.v, periodo(MU, e.r, e.v))
        self.assertLess(norma(sub(r, e.r)), 1e-3)
        self.assertLess(norma(sub(v, e.v)), 1e-6)

    def test_uma_volta_eliptica_volta_ao_inicio(self):
        for e in (HOJE_NAVE, HOJE_ALVO):
            r, v = propagar(MU, e.r, e.v, periodo(MU, e.r, e.v))
            self.assertLess(norma(sub(r, e.r)), 1e-3)
            self.assertLess(norma(sub(v, e.v)), 1e-6)

    def test_varias_voltas_e_fracao(self):
        r, v = propagar(MU, HOJE_ALVO.r, HOJE_ALVO.v, 10 * periodo(MU, HOJE_ALVO.r, HOJE_ALVO.v))
        self.assertLess(norma(sub(r, HOJE_ALVO.r)), 1e-2)

    def test_bate_com_a_integracao_passo_a_passo(self):
        raio = KERBIN.raio + 200_000.0
        r = (raio, 0.0, 0.0)
        v = (0.0, 0.0, -math.sqrt(MU / raio) * 1.05)
        e = elementos(KERBIN, r, v)[1]
        self.assertAlmostEqual(e, 0.1025, delta=0.01)
        dt = 3 * periodo(MU, r, v)
        r_k, v_k = propagar(MU, r, v, dt)
        r_i, v_i = rk4(MU, r, v, dt, 1.0)
        self.assertLess(norma(sub(r_k, r_i)), 0.5)
        self.assertLess(norma(sub(v_k, v_i)), 1e-3)

    def test_dt_negativo_desfaz_o_positivo(self):
        for e in (HOJE_NAVE, circular(KERBIN, 100_000.0, 200.0)):
            for dt in (123.4, 3000.0, 7 * 2207.0 + 55.0):
                r, v = propagar(MU, e.r, e.v, dt)
                r0, v0 = propagar(MU, r, v, -dt)
                self.assertLess(norma(sub(r0, e.r)), 1e-3)
                self.assertLess(norma(sub(v0, e.v)), 1e-6)

    def test_conserva_energia_e_momento_angular(self):
        e = HOJE_ALVO
        h0 = cruz(e.r, e.v)
        e0 = energia(MU, e.r, e.v)
        for dt in (100.0, 1234.5, 5 * 2207.7 + 321.0, -2000.0):
            r, v = propagar(MU, e.r, e.v, dt)
            self.assertLess(norma(sub(cruz(r, v), h0)) / norma(h0), 1e-10)
            self.assertLess(abs(energia(MU, r, v) - e0) / abs(e0), 1e-10)

    def test_escape_levanta_valueerror(self):
        e = circular(KERBIN, 100_000.0, 0.0)
        rapido = esc(1.5, e.v)
        with self.assertRaises(ValueError):
            propagar(MU, e.r, rapido, 100.0)
        parabolica = esc(math.sqrt(2.0), e.v)
        with self.assertRaises(ValueError):
            propagar(MU, e.r, parabolica, 100.0)
        with self.assertRaises(ValueError):
            periodo(MU, e.r, rapido)

    def test_periodo_circular(self):
        e = circular(KERBIN, 158_000.0, 0.0)
        a = KERBIN.raio + 158_000.0
        self.assertAlmostEqual(periodo(MU, e.r, e.v), 2 * math.pi * math.sqrt(a**3 / MU), places=6)


class TestMenorDistancia(unittest.TestCase):
    def test_mesma_orbita_circular_com_10_graus(self):
        nave = circular(KERBIN, 150_000.0, 0.0)
        alvo = circular(KERBIN, 150_000.0, 10.0)
        raio = KERBIN.raio + 150_000.0
        corda = 2.0 * raio * math.sin(math.radians(5.0))
        t = periodo(MU, nave.r, nave.v)
        for t_ini, t_fim in ((UT_HOJE, UT_HOJE + t), (UT_HOJE, UT_HOJE + 3.3 * t)):
            d, tm, v_rel = menor_distancia(MU, nave, alvo, t_ini, t_fim)
            self.assertAlmostEqual(d, corda, delta=1e-3)
            self.assertGreaterEqual(tm, t_ini)
            self.assertLessEqual(tm, t_fim)
            self.assertAlmostEqual(v_rel, 2.0 * norma(nave.v) * math.sin(math.radians(5.0)), delta=1e-3)

    def test_orbita_baixada_encontra_o_alvo_no_ponto_da_queima(self):
        k = 3
        ponto_queima = circular(KERBIN, 150_000.0, 0.0)
        t_alvo = periodo(MU, ponto_queima.r, ponto_queima.v)
        t_tr = 0.8 * t_alvo
        a_tr = (MU * (t_tr / (2 * math.pi)) ** 2) ** (1.0 / 3.0)
        v_apo = math.sqrt(MU * (2.0 / norma(ponto_queima.r) - 1.0 / a_tr))
        dv = norma(ponto_queima.v) - v_apo
        nave = Estado(UT_HOJE, ponto_queima.r, esc(v_apo / norma(ponto_queima.v), ponto_queima.v))
        tm = UT_HOJE + k * t_tr
        r_a, v_a = propagar(MU, ponto_queima.r, ponto_queima.v, UT_HOJE - tm)
        alvo = Estado(UT_HOJE, r_a, v_a)
        self.assertGreater(dv, 10.0)
        d, t, v_rel = menor_distancia(MU, nave, alvo, UT_HOJE + 100.0, tm + 1000.0)
        self.assertLess(d, 0.5)
        self.assertAlmostEqual(t, tm, delta=0.5)
        self.assertAlmostEqual(v_rel, dv, delta=0.01)

    def test_janela_curta_nao_sai_do_intervalo(self):
        nave = circular(KERBIN, 150_000.0, 0.0)
        alvo = circular(KERBIN, 150_000.0, 10.0)
        d, t, _ = menor_distancia(MU, nave, alvo, UT_HOJE + 500.0, UT_HOJE + 520.0)
        self.assertGreaterEqual(t, UT_HOJE + 500.0)
        self.assertLessEqual(t, UT_HOJE + 520.0)


def montar_interceptacao(dv_verdadeiro, fracao_de_volta, altitude=150_000.0):
    """(nave, alvo, tm, dv_verdadeiro): uma nave que erra a mira por quilômetros sem queimar."""
    nave = circular(KERBIN, altitude, 0.0)
    tm = UT_HOJE + fracao_de_volta * periodo(MU, nave.r, nave.v)
    r_m, _ = propagar(MU, nave.r, soma(nave.v, dv_verdadeiro), tm - UT_HOJE)
    r_alvo = sub(r_m, esc(D_MIRA, unit(r_m)))
    v_alvo = esc(math.sqrt(MU / norma(r_alvo)), unit(cruz(POLO, r_alvo)))
    r0, v0 = propagar(MU, r_alvo, v_alvo, UT_HOJE - tm)
    return nave, Estado(UT_HOJE, r0, v0), tm


class TestInterceptar(unittest.TestCase):
    def test_erro_de_5_km_a_0_3_volta(self):
        dv_verdadeiro = (6.0, -4.0, 8.0)
        nave, alvo, tm = montar_interceptacao(dv_verdadeiro, 0.3)
        r_sem, _ = propagar(MU, nave.r, nave.v, tm - UT_HOJE)
        r_alvo_m, v_alvo_m = propagar(MU, alvo.r, alvo.v, tm - UT_HOJE)
        mira = soma(r_alvo_m, esc(D_MIRA, unit(r_alvo_m)))
        self.assertGreater(norma(sub(r_sem, mira)), 4_000.0)
        dv = interceptar(MU, nave, UT_HOJE, alvo, tm, (0.0, 0.0, 0.0))
        self.assertIsNotNone(dv)
        r, _ = propagar(MU, nave.r, soma(nave.v, dv), tm - UT_HOJE)
        self.assertLess(norma(sub(r, mira)), 0.5)
        self.assertLess(norma(dv), 15.0)
        self.assertLess(norma(sub(dv, dv_verdadeiro)), 0.5)

    def test_instante_diferente_do_estado(self):
        dv_verdadeiro = (6.0, -4.0, 8.0)
        nave, alvo, tm = montar_interceptacao(dv_verdadeiro, 0.3)
        antes = Estado(UT_HOJE - 500.0, *propagar(MU, nave.r, nave.v, -500.0))
        dv = interceptar(MU, antes, UT_HOJE, alvo, tm, (0.0, 0.0, 0.0))
        self.assertIsNotNone(dv)
        self.assertLess(norma(sub(dv, dv_verdadeiro)), 0.5)

    def test_em_voltas_inteiras_devolve_none_ou_converge(self):
        for volta in (1.0, 2.0, 3.0):
            nave, alvo, tm = montar_interceptacao((6.0, -4.0, 8.0), volta)
            dv = interceptar(MU, nave, UT_HOJE, alvo, tm, (0.0, 0.0, 0.0))
            if dv is not None:
                r, _ = propagar(MU, nave.r, soma(nave.v, dv), tm - UT_HOJE)
                r_alvo_m, _ = propagar(MU, alvo.r, alvo.v, tm - UT_HOJE)
                mira = soma(r_alvo_m, esc(D_MIRA, unit(r_alvo_m)))
                self.assertLess(norma(sub(r, mira)), 0.5)

    def test_nao_salta_para_escape(self):
        nave = circular(KERBIN, 150_000.0, 0.0)
        longe = circular(KERBIN, 20_000_000.0, 100.0)
        for tm in (UT_HOJE + 600.0, UT_HOJE + 0.3 * 2207.0, UT_HOJE + 2.4 * 2207.0):
            for dv0 in ((0.0, 0.0, 0.0), (0.0, 0.0, -3000.0), (500.0, 200.0, 100.0)):
                dv = interceptar(MU, nave, UT_HOJE, longe, tm, dv0)
                if dv is not None:
                    self.assertTrue(math.isfinite(elementos(KERBIN, nave.r, soma(nave.v, dv))[0]))

    def test_tempo_de_voo_negativo_devolve_none(self):
        nave, alvo, tm = montar_interceptacao((6.0, -4.0, 8.0), 0.3)
        self.assertIsNone(interceptar(MU, nave, tm + 10.0, alvo, tm, (0.0, 0.0, 0.0)))


class TestChute(unittest.TestCase):
    def test_uma_volta_sem_fase_nao_muda_nada(self):
        e = circular(KERBIN, 150_000.0, 0.0)
        t = periodo(MU, e.r, e.v)
        dv = chute_tangencial(MU, e.r, e.v, 0.0, t, 1.0)
        self.assertLess(norma(dv), 1e-6)

    def test_mais_voltas_pede_orbita_menor_e_freia(self):
        e = circular(KERBIN, 150_000.0, 0.0)
        t = periodo(MU, e.r, e.v)
        dv = chute_tangencial(MU, e.r, e.v, 0.25, t, 1.0)
        self.assertLess(ponto(dv, e.v), 0.0)
        self.assertAlmostEqual(ponto(unit(dv), unit(e.v)), -1.0, places=9)
        dv = chute_tangencial(MU, e.r, e.v, -0.25, t, 1.0)
        self.assertGreater(ponto(dv, e.v), 0.0)

    def test_hohmann_para_cima(self):
        e = circular(KERBIN, 100_000.0, 0.0)
        r2 = KERBIN.raio + 158_000.0
        a = (norma(e.r) + r2) / 2.0
        t_tr = 2 * math.pi * math.sqrt(a**3 / MU)
        dv = chute_tangencial(MU, e.r, e.v, 0.0, t_tr / 2.0, 0.5)
        esperado = math.sqrt(MU * (2.0 / norma(e.r) - 1.0 / a)) - norma(e.v)
        self.assertAlmostEqual(norma(dv), esperado, delta=1e-6)

    def test_sem_solucao_devolve_none(self):
        e = circular(KERBIN, 150_000.0, 0.0)
        self.assertIsNone(chute_tangencial(MU, e.r, e.v, 0.0, 100.0, 0.2))
        self.assertIsNone(chute_tangencial(MU, e.r, e.v, 0.0, 100.0, 30.0))


def verificar_encontro(caso, planeta, nave, alvo, tr):
    """A queima planejada leva a nave à mira, com a velocidade relativa anunciada."""
    mu = planeta.mu
    r1, v1 = propagar(mu, nave.r, nave.v, tr.t1 - nave.t)
    r, v = propagar(mu, r1, soma(v1, tr.dv1), tr.tm - tr.t1)
    r_a, v_a = propagar(mu, alvo.r, alvo.v, tr.tm - alvo.t)
    caso.assertAlmostEqual(norma(sub(r, r_a)), D_MIRA, delta=1.0)
    caso.assertAlmostEqual(norma(sub(v, v_a)), tr.v_rel, delta=1e-3)
    caso.assertAlmostEqual(tr.dv_total, norma(tr.dv1) + tr.v_rel, delta=1e-6)
    caso.assertGreaterEqual(tr.t1, nave.t + rendezvous.ESPERA_MIN - 1e-6)
    return elementos(planeta, r1, soma(v1, tr.dv1))


class TestPlanejarTransferencia(unittest.TestCase):
    def test_caso_de_hoje(self):
        tr = planejar_transferencia(KERBIN, HOJE_NAVE, HOJE_ALVO, UT_HOJE, 6)
        self.assertIsNotNone(tr)
        _, _, ra, rp = verificar_encontro(self, KERBIN, HOJE_NAVE, HOJE_ALVO, tr)
        self.assertLess(tr.dv_total, 40.0)
        self.assertGreater(rp - KERBIN.raio, 75_000.0)
        self.assertGreater(tr.voltas, 0.3)

    def test_de_100_e_de_200_km_ate_158_km(self):
        for altitude, fases in ((100_000.0, (0.0, 90.0, 180.0, 270.0)), (200_000.0, (0.0, 90.0, 180.0, 270.0))):
            hoh = hohmann(MU, KERBIN.raio + altitude, KERBIN.raio + 158_000.0)
            for fase in fases:
                with self.subTest(altitude=altitude, fase=fase):
                    nave = circular(KERBIN, altitude, 0.0)
                    alvo = circular(KERBIN, 158_000.0, fase)
                    tr = planejar_transferencia(KERBIN, nave, alvo, UT_HOJE, 6)
                    self.assertIsNotNone(tr)
                    verificar_encontro(self, KERBIN, nave, alvo, tr)
                    self.assertLess(tr.dv_total, 1.05 * hoh)

    def test_de_80_km_ate_158_km_exige_o_periodo_sinodico(self):
        hoh = hohmann(MU, KERBIN.raio + 80_000.0, KERBIN.raio + 158_000.0)
        for fase in (0.0, 120.0, 240.0):
            with self.subTest(fase=fase):
                nave = circular(KERBIN, 80_000.0, 0.0)
                alvo = circular(KERBIN, 158_000.0, fase)
                tr = planejar_transferencia(KERBIN, nave, alvo, UT_HOJE, 6)
                self.assertIsNotNone(tr)
                _, _, _, rp = verificar_encontro(self, KERBIN, nave, alvo, tr)
                self.assertGreater(rp - KERBIN.raio, KERBIN.topo + FOLGA_AR)
                self.assertLess(tr.dv_total, 1.10 * hoh)

    def test_alvo_a_frente_e_atras(self):
        for fase in (45.0, -45.0):
            with self.subTest(fase=fase):
                nave = circular(KERBIN, 158_000.0, 0.0)
                alvo = circular(KERBIN, 158_000.0, fase)
                tr = planejar_transferencia(KERBIN, nave, alvo, UT_HOJE, 6)
                self.assertIsNotNone(tr)
                _, _, _, rp = verificar_encontro(self, KERBIN, nave, alvo, tr)
                self.assertGreater(rp - KERBIN.raio, KERBIN.topo + FOLGA_AR)
                self.assertLess(tr.dv_total, 60.0)

    def test_sem_solucao_com_uma_volta_e_alvo_a_180_graus(self):
        nave = circular(KERBIN, 158_000.0, 0.0)
        alvo = circular(KERBIN, 158_000.0, 180.0)
        self.assertIsNone(planejar_transferencia(KERBIN, nave, alvo, UT_HOJE, 1))

    def test_na_mun_respeita_folga_do_chao(self):
        nave = circular(MUN, 30_000.0, 0.0)
        alvo = circular(MUN, 40_000.0, 60.0)
        tr = planejar_transferencia(MUN, nave, alvo, UT_HOJE, 6)
        self.assertIsNotNone(tr)
        _, _, ra, rp = verificar_encontro(self, MUN, nave, alvo, tr)
        self.assertGreater(rp - MUN.raio, FOLGA_CHAO)
        self.assertLess(ra, MUN.soi)

    def test_na_mun_nave_baixa_nao_desce_mais(self):
        nave = circular(MUN, 12_000.0, 0.0)
        alvo = circular(MUN, 40_000.0, 100.0)
        tr = planejar_transferencia(MUN, nave, alvo, UT_HOJE, 6)
        self.assertIsNotNone(tr)
        _, _, _, rp = verificar_encontro(self, MUN, nave, alvo, tr)
        self.assertGreater(rp - MUN.raio, FOLGA_CHAO)

    def test_orbita_aberta_levanta_valueerror(self):
        nave = circular(KERBIN, 158_000.0, 0.0)
        fugindo = Estado(UT_HOJE, nave.r, esc(1.6, nave.v))
        with self.assertRaises(ValueError):
            planejar_transferencia(KERBIN, fugindo, circular(KERBIN, 158_000.0, 45.0), UT_HOJE, 6)


class TestWNo(unittest.TestCase):
    def setUp(self):
        self.nave = HOJE_NAVE
        self.tr = planejar_transferencia(KERBIN, HOJE_NAVE, HOJE_ALVO, UT_HOJE, 6)
        self.r1, self.v1 = propagar(MU, self.nave.r, self.nave.v, self.tr.t1 - self.nave.t)
        self.v_depois = soma(self.v1, self.tr.dv1)

    def test_antes_da_queima_e_o_plano(self):
        w = w_no(MU, self.nave, self.tr.t1, self.v_depois)
        self.assertLess(norma(sub(w, self.tr.dv1)), 1e-6)
        w = w_no(MU, Estado(self.tr.t1, self.r1, self.v1), self.tr.t1, self.v_depois)
        self.assertLess(norma(sub(w, self.tr.dv1)), 1e-9)

    def test_zero_logo_depois_de_uma_queima_instantanea(self):
        depois = Estado(self.tr.t1, self.r1, self.v_depois)
        self.assertLess(norma(w_no(MU, depois, self.tr.t1, self.v_depois)), 1e-9)

    def test_zero_em_qualquer_instante_depois(self):
        depois = Estado(self.tr.t1, self.r1, self.v_depois)
        for dt in (10.0, 600.0, 5000.0):
            r, v = propagar(MU, depois.r, depois.v, dt)
            self.assertLess(norma(w_no(MU, Estado(depois.t + dt, r, v), self.tr.t1, self.v_depois)), 1e-6)

    def test_durante_a_queima_cai_em_direcao_a_zero(self):
        meio = Estado(self.tr.t1, self.r1, soma(self.v1, esc(0.5, self.tr.dv1)))
        w = w_no(MU, meio, self.tr.t1, self.v_depois)
        self.assertLess(norma(sub(w, esc(0.5, self.tr.dv1))), 1e-9)


class TestNoRelativo(unittest.TestCase):
    def test_tempo_ate_o_no_bate_com_a_geometria(self):
        nave = circular(KERBIN, 150_000.0, 0.0)
        n_atual = unit(cruz(nave.r, nave.v))
        omega = math.sqrt(MU / norma(nave.r) ** 3)
        for graus, esperado in ((30.0, 30.0), (200.0, 20.0), (170.0, 170.0), (350.0, 170.0)):
            with self.subTest(graus=graus):
                no = rotacionar(unit(nave.r), n_atual, math.radians(graus))
                n_alvo = rotacionar(n_atual, no, math.radians(0.5))
                self.assertAlmostEqual(angulo(n_atual, n_alvo), 0.5, places=6)
                dt, u = no_relativo(KERBIN, nave.r, nave.v, n_alvo)
                self.assertAlmostEqual(dt, math.radians(esperado) / omega, delta=1e-3)
                self.assertAlmostEqual(abs(ponto(u, no)), 1.0, places=6)

    def test_mesmo_plano_nao_espera(self):
        nave = circular(KERBIN, 150_000.0, 40.0)
        dt, _ = no_relativo(KERBIN, nave.r, nave.v, unit(cruz(nave.r, nave.v)))
        self.assertTrue(math.isfinite(dt))


class TestDvDisponivel(unittest.TestCase):
    def test_equacao_do_foguete(self):
        self.assertAlmostEqual(dv_disponivel(10_256.234375, 3_000.0, 355.0), 355.0 * 9.80665 * math.log(10_256.234375 / 7_256.234375))
        self.assertAlmostEqual(dv_disponivel(2.0, 1.0, 100.0), 100.0 * 9.80665 * math.log(2.0))
        self.assertEqual(dv_disponivel(5.0, 0.0, 300.0), 0.0)


if __name__ == "__main__":
    unittest.main()
