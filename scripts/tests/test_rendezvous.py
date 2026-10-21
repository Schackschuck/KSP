"""Testes das contas do rendezvous (rendezvous.py), sem o KSP.

Uso, a partir da raiz do repositório:
    python scripts/tests/test_rendezvous.py
    python scripts/tests/test_rendezvous.py -v    # uma linha por teste
"""

import argparse
import contextlib
import io
import math
import os
import re
import sys
import time
import types
import unittest
from dataclasses import dataclass
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import rendezvous
from rendezvous import (
    APROXIMA,
    CORRECAO,
    Comando,
    D_MIRA,
    ENCONTRO,
    FALHA,
    FOLGA_AR,
    FOLGA_CHAO,
    G0,
    PLANO,
    TRANSFERENCIA,
    VELOCIDADE,
    Estado,
    Guiagem,
    NaveOrbital,
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


MASSA_MODULO = 10_256.234375
COMBUSTIVEL_MODULO = 3_000.0
EMPUXO_MODULO = 125_000.0
ISP_MODULO = 355.0
T_MAX_VOO = 60_000.0
D_FINAL = 100.0


@dataclass
class Voo:
    """O resultado de um voo na NaveOrbital: o fim, as fases em ordem, os números e os extremos do caminho."""

    fase: str
    aviso: str
    fases: list
    distancia: float
    v_rel: float
    dv: float
    dv_guiagem: float
    distancia_minima: float
    periastro_minimo: float
    t_jogo: float
    t_real: float


def montar(nave, alvo, combustivel=COMBUSTIVEL_MODULO):
    return NaveOrbital(KERBIN, nave, alvo, MASSA_MODULO, combustivel, EMPUXO_MODULO, ISP_MODULO)


def voar(nave, guiagem, t_max=T_MAX_VOO, passo=0.05):
    """Roda a Guiagem na NaveOrbital, a 20 Hz de jogo, até ENCONTRO ou FALHA (ou t_max s de jogo)."""
    inicio = time.monotonic()
    t0, massa0 = nave.t, nave.massa
    fases = []
    d_min = periastro_min = math.inf
    while True:
        l = nave.leitura()
        comando = guiagem.passo(l)
        if not fases or fases[-1] != guiagem.fase:
            fases.append(guiagem.fase)
        if l.alvo is not None:
            d_min = min(d_min, norma(sub(l.alvo.r, l.r)))
        periastro_min = min(periastro_min, elementos(KERBIN, l.r, l.v)[3] - KERBIN.raio)
        if guiagem.fase in (ENCONTRO, FALHA) or l.t - t0 > t_max:
            break
        nave.executar(comando)
        nave.avancar(passo)
    l = nave.leitura()
    return Voo(
        fase=guiagem.fase,
        aviso=guiagem.aviso,
        fases=fases,
        distancia=norma(sub(l.alvo.r, l.r)),
        v_rel=norma(sub(l.v, l.alvo.v)),
        dv=nave.isp * nave.fator_isp * G0 * math.log(massa0 / nave.massa),
        dv_guiagem=guiagem.dv,
        distancia_minima=d_min,
        periastro_minimo=periastro_min,
        t_jogo=l.t - t0,
        t_real=time.monotonic() - inicio,
    )


class TestVoos(unittest.TestCase):
    def conferir(self, voo, dv_max, d_final=D_FINAL):
        self.assertEqual(voo.fase, ENCONTRO, voo)
        self.assertLess(voo.distancia, d_final + 50.0, voo)
        self.assertLess(voo.v_rel, 0.3, voo)
        self.assertLess(voo.dv, dv_max, voo)
        self.assertGreater(voo.periastro_minimo, KERBIN.topo + FOLGA_AR, voo)
        self.assertGreater(voo.distancia_minima, d_final - 50.0, voo)

    def test_caso_de_hoje(self):
        voo = voar(montar(HOJE_NAVE, HOJE_ALVO), Guiagem(KERBIN, D_FINAL, 6))
        self.conferir(voo, 50.0)
        self.assertEqual(voo.fases, [TRANSFERENCIA, CORRECAO, VELOCIDADE, APROXIMA, ENCONTRO])

    def test_alvo_a_frente(self):
        nave = circular(KERBIN, 158_000.0, 0.0)
        voo = voar(montar(nave, circular(KERBIN, 158_000.0, 45.0)), Guiagem(KERBIN, D_FINAL, 6))
        self.conferir(voo, 80.0)

    def test_de_100_km_ate_158_km(self):
        hoh = hohmann(MU, KERBIN.raio + 100_000.0, KERBIN.raio + 158_000.0)
        for fase in (90.0, 270.0):
            with self.subTest(fase=fase):
                nave = circular(KERBIN, 100_000.0, 0.0)
                voo = voar(montar(nave, circular(KERBIN, 158_000.0, fase)), Guiagem(KERBIN, D_FINAL, 6))
                self.conferir(voo, 1.4 * hoh + 20.0)

    def test_diferenca_de_plano_de_meio_grau(self):
        n_alvo = rotacionar(POLO, (1.0, 0.0, 0.0), math.radians(0.5))
        nave = circular(KERBIN, 158_000.0, 100.0)
        alvo = circular(KERBIN, 158_000.0, 150.0, normal=n_alvo)
        self.assertAlmostEqual(angulo(unit(cruz(nave.r, nave.v)), unit(cruz(alvo.r, alvo.v))), 0.5, places=6)
        voo = voar(montar(nave, alvo), Guiagem(KERBIN, D_FINAL, 6))
        self.conferir(voo, 80.0)
        self.assertEqual(voo.fases[0], PLANO)

    def test_motor_cortado_antes_de_planejar_a_transferencia(self):
        n_alvo = rotacionar(POLO, (1.0, 0.0, 0.0), math.radians(0.5))
        nave = montar(circular(KERBIN, 158_000.0, 100.0), circular(KERBIN, 158_000.0, 150.0, normal=n_alvo))
        guiagem = Guiagem(KERBIN, D_FINAL, 6)
        anterior = None
        while guiagem.transferencia is None:
            comando = guiagem.passo(nave.leitura())
            self.assertNotEqual(guiagem.fase, FALHA)
            if guiagem.transferencia is None:
                anterior = comando
                nave.executar(comando)
                nave.avancar(0.05)
        self.assertEqual(anterior.acelerador, 0.0)

    def test_nariz_que_vira_devagar(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        nave.giro_max = 1.0
        guiagem = Guiagem(KERBIN, D_FINAL, 6)
        voo = voar(nave, guiagem)
        self.conferir(voo, 50.0)
        self.assertAlmostEqual(guiagem._giro, 1.0, delta=0.2)

    def test_empuxo_e_isp_errados_em_3_por_cento(self):
        for campo, fator in (("fator_empuxo", 0.97), ("fator_empuxo", 1.03), ("fator_isp", 0.97), ("fator_isp", 1.03)):
            with self.subTest(campo=campo, fator=fator):
                nave = montar(HOJE_NAVE, HOJE_ALVO)
                setattr(nave, campo, fator)
                voo = voar(nave, Guiagem(KERBIN, D_FINAL, 6))
                self.conferir(voo, 60.0)

    def test_alvo_a_2_km_vai_direto_para_a_velocidade(self):
        raio = KERBIN.raio + 158_000.0
        graus = math.degrees(2_000.0 / raio)
        nave = circular(KERBIN, 158_000.0, 0.0)
        for fator in (1.0, 1.0003):
            with self.subTest(fator=fator):
                alvo = circular(KERBIN, 158_000.0, graus)
                alvo = Estado(alvo.t, alvo.r, esc(fator, alvo.v))
                voo = voar(montar(nave, alvo), Guiagem(KERBIN, D_FINAL, 6))
                self.conferir(voo, 30.0)
                self.assertEqual(voo.fases, [VELOCIDADE, APROXIMA, ENCONTRO])

    def test_pouco_combustivel_falha_antes_de_queimar(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO, combustivel=100.0)
        voo = voar(nave, Guiagem(KERBIN, D_FINAL, 6))
        self.assertEqual(voo.fase, FALHA)
        self.assertEqual(voo.aviso, "COMBUSTIVEL")
        self.assertEqual(voo.fases, [FALHA])
        self.assertEqual(voo.dv, 0.0)
        self.assertEqual(voo.dv_guiagem, 0.0)

    def test_distancia_final_diferente(self):
        voo = voar(montar(HOJE_NAVE, HOJE_ALVO), Guiagem(KERBIN, 200.0, 6))
        self.conferir(voo, 50.0, d_final=200.0)


class TestNaveOrbital(unittest.TestCase):
    def test_sem_motor_bate_com_propagar(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        nave.avancar(600.0)
        r, v = propagar(MU, HOJE_NAVE.r, HOJE_NAVE.v, 600.0)
        self.assertLess(norma(sub(nave.r, r)), 1.0)
        self.assertLess(norma(sub(nave.v, v)), 1e-3)
        self.assertAlmostEqual(nave.t, UT_HOJE + 600.0, delta=1e-3)

    def test_acelerar_ate_pula_nave_e_alvo_por_kepler(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        nave.executar(Comando(0.0, (1.0, 0.0, 0.0), acelerar_ate=UT_HOJE + 5_000.0))
        r, v = propagar(MU, HOJE_NAVE.r, HOJE_NAVE.v, 5_000.0)
        ra, va = propagar(MU, HOJE_ALVO.r, HOJE_ALVO.v, 5_000.0)
        l = nave.leitura()
        self.assertEqual(l.t, UT_HOJE + 5_000.0)
        self.assertLess(norma(sub(l.r, r)), 1e-6)
        self.assertLess(norma(sub(l.alvo.r, ra)), 1e-6)
        self.assertLess(norma(sub(l.alvo.v, va)), 1e-9)
        self.assertEqual(l.alvo.t, l.t)

    def test_queima_gasta_o_delta_v_da_equacao_do_foguete(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        nave.nariz = unit(HOJE_NAVE.v)
        v0 = norma(nave.v)
        nave.executar(Comando(1.0, nave.nariz))
        nave.avancar(10.0)
        esperado = ISP_MODULO * G0 * math.log(MASSA_MODULO / nave.massa)
        self.assertAlmostEqual(MASSA_MODULO - nave.massa, EMPUXO_MODULO / (ISP_MODULO * G0) * 10.0, delta=0.01)
        self.assertAlmostEqual(norma(nave.v) - v0, esperado, delta=0.1 * esperado / 100.0 + 0.2)
        self.assertEqual(nave.leitura().empuxo, EMPUXO_MODULO)

    def test_o_nariz_gira_no_maximo_a_taxa_pedida(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        nave.nariz = (1.0, 0.0, 0.0)
        nave.executar(Comando(0.0, (0.0, 1.0, 0.0)))
        nave.avancar(10.0)
        self.assertAlmostEqual(angulo(nave.nariz, (1.0, 0.0, 0.0)), 50.0, delta=1e-6)
        nave.avancar(10.0)
        self.assertAlmostEqual(angulo(nave.nariz, (0.0, 1.0, 0.0)), 0.0, delta=1e-6)

    def test_nariz_vira_ate_do_lado_oposto(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        nave.nariz = (1.0, 0.0, 0.0)
        nave.executar(Comando(0.0, (-1.0, 0.0, 0.0)))
        nave.avancar(10.0)
        self.assertAlmostEqual(angulo(nave.nariz, (1.0, 0.0, 0.0)), 50.0, delta=1e-6)

    def test_sem_combustivel_a_leitura_nao_tem_empuxo(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO, combustivel=0.0)
        l = nave.leitura()
        self.assertEqual((l.empuxo, l.isp), (0.0, 0.0))


class TestGuiagemPassoAPasso(unittest.TestCase):
    def test_sem_alvo_e_alvo(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        l = nave.leitura()
        l.alvo = None
        g = Guiagem(KERBIN, D_FINAL, 6)
        comando = g.passo(l)
        self.assertEqual((g.fase, g.aviso, comando.acelerador), (FALHA, "ALVO", 0.0))

    def test_orbita_dentro_do_ar_e_orbita(self):
        baixa = circular(KERBIN, 50_000.0, 0.0)
        for nave, alvo in ((baixa, HOJE_ALVO), (HOJE_NAVE, baixa)):
            g = Guiagem(KERBIN, D_FINAL, 6)
            g.passo(montar(nave, alvo).leitura())
            self.assertEqual((g.fase, g.aviso), (FALHA, "ORBITA"))

    def test_orbita_aberta_e_orbita(self):
        fugindo = Estado(UT_HOJE, HOJE_NAVE.r, esc(1.6, HOJE_NAVE.v))
        g = Guiagem(KERBIN, D_FINAL, 6)
        g.passo(montar(fugindo, HOJE_ALVO).leitura())
        self.assertEqual((g.fase, g.aviso), (FALHA, "ORBITA"))

    def test_sem_transferencia_e_transferencia(self):
        nave = circular(KERBIN, 158_000.0, 0.0)
        g = Guiagem(KERBIN, D_FINAL, 1)
        g.passo(montar(nave, circular(KERBIN, 158_000.0, 180.0)).leitura())
        self.assertEqual((g.fase, g.aviso), (FALHA, "TRANSFERENCIA"))

    def test_motor_apagado_e_combustivel(self):
        g = Guiagem(KERBIN, D_FINAL, 6)
        g.passo(montar(HOJE_NAVE, HOJE_ALVO, combustivel=0.0).leitura())
        self.assertEqual((g.fase, g.aviso), (FALHA, "COMBUSTIVEL"))

    def test_plano_e_a_primeira_fase_com_o_plano_diferente(self):
        n_alvo = rotacionar(POLO, (1.0, 0.0, 0.0), math.radians(0.5))
        nave = circular(KERBIN, 158_000.0, 100.0)
        alvo = circular(KERBIN, 158_000.0, 150.0, normal=n_alvo)
        g = Guiagem(KERBIN, D_FINAL, 6)
        comando = g.passo(montar(nave, alvo).leitura())
        self.assertEqual(g.fase, PLANO)
        self.assertTrue(comando.no_mudou)
        self.assertEqual(comando.acelerador, 0.0)
        self.assertGreater(g.dv_proxima, 10.0)

    def test_a_primeira_leitura_planeja_e_mostra_o_no(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        g = Guiagem(KERBIN, D_FINAL, 6)
        comando = g.passo(nave.leitura())
        tr = g.transferencia
        self.assertEqual(g.fase, TRANSFERENCIA)
        self.assertIsNotNone(tr)
        self.assertEqual(comando.no, (tr.t1, tr.dv1))
        self.assertTrue(comando.no_mudou)
        self.assertEqual(g.proxima_queima, tr.t1)
        self.assertAlmostEqual(g.dv_proxima, norma(tr.dv1))
        self.assertGreater(comando.acelerar_ate, UT_HOJE)
        seguinte = g.passo(nave.leitura())
        self.assertFalse(seguinte.no_mudou)
        self.assertEqual(seguinte.no, comando.no)

    def test_o_no_muda_so_quando_muda_e_some_no_fim(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        g = Guiagem(KERBIN, D_FINAL, 6)
        nos = []
        atual = None
        while True:
            l = nave.leitura()
            comando = g.passo(l)
            if comando.no_mudou:
                nos.append(comando.no)
            else:
                self.assertEqual(comando.no, atual)
            atual = comando.no
            if g.fase in (ENCONTRO, FALHA):
                break
            nave.executar(comando)
            nave.avancar(0.05)
        self.assertEqual(g.fase, ENCONTRO)
        self.assertIsNone(nos[-1])
        self.assertIsNone(comando.no)
        self.assertEqual(g.dv_proxima, 0.0)
        self.assertIsNone(g.proxima_queima)
        self.assertEqual(nos[0], (g.transferencia.t1, g.transferencia.dv1))
        for anterior, seguinte in zip(nos, nos[1:]):
            self.assertNotEqual(anterior, seguinte)


NR = "nr"
SUP = "sup"
SEM_CONICAS = "o jogo não deixa criar nós agora"


class FluxoFalso:
    def __init__(self, funcao, argumentos):
        self.funcao = funcao
        self.argumentos = argumentos
        self.removido = False

    def __call__(self):
        return self.funcao(*self.argumentos)

    def remove(self):
        self.removido = True


class NoFalso:
    """Um nó de manobra do jogo, com a base de prograde, normal e radial calculada à parte da guiagem."""

    def __init__(self, jogo, ut, prograde, normal, radial):
        self.jogo = jogo
        self.ut = ut
        self.prograde = prograde
        self.normal = normal
        self.radial = radial
        self.removido = False
        sim = jogo.sim
        self._r, self._v = propagar(MU, sim.r, sim.v, ut - sim.t)
        p = unit(self._v)
        n = unit(cruz(self._r, self._v))
        fora = unit(sub(self._r, esc(ponto(self._r, p), p)))
        self._dv = soma(soma(esc(prograde, p), esc(normal, n)), esc(radial, fora))
        self._alvo = sim.alvo()

    def remove(self):
        if not self.removido:
            self.jogo.nave.control.nodes.remove(self)
        self.removido = True

    def burn_vector(self, referencia):
        return self.jogo.eixos(self._dv)

    @property
    def orbit(self):
        depois = Estado(self.ut, self._r, soma(self._v, self._dv))

        def menor(outra):
            return menor_distancia(MU, depois, self._alvo, self.ut, self.ut + 15 * 2207.0)

        return types.SimpleNamespace(
            distance_at_closest_approach=lambda outra: menor(outra)[0],
            time_of_closest_approach=lambda outra: menor(outra)[1],
        )


class RecursosFalsos:
    def __init__(self, nomes):
        self.nomes = nomes

    def has_resource(self, nome):
        return nome in self.nomes


class PecaFalsa:
    def __init__(self, decouple_stage, dry_mass, recursos, combustivel=lambda: 0.0):
        self.decouple_stage = decouple_stage
        self.dry_mass = dry_mass
        self.resources = RecursosFalsos(recursos)
        self._combustivel = combustivel

    @property
    def mass(self):
        return self.dry_mass + self._combustivel()


class MotorFalso:
    def __init__(self, peca, propellant_names, active=True):
        self.part = peca
        self.propellant_names = propellant_names
        self.active = active


class SuperficieFalsa:
    def __init__(self, roll=True):
        self.pitch_enabled = True
        self.yaw_enabled = True
        self.roll_enabled = roll


class PartesFalsas:
    def __init__(self, jogo):
        sim = jogo.sim
        combustiveis = ["LiquidFuel", "Oxidizer"]
        self.tanque = PecaFalsa(1, 1_000.0, combustiveis, lambda: sim.combustivel)
        self.peca_motor = PecaFalsa(1, 500.0, [])
        self.tanque_mono = PecaFalsa(1, 100.0, ["MonoPropellant"], lambda: 200.0)
        self.carga = PecaFalsa(2, 200.0, ["LiquidFuel"], lambda: 600.0)
        self.peca_motor_de_cima = PecaFalsa(2, 300.0, [])
        self.motor = MotorFalso(self.peca_motor, combustiveis)
        self.motor_de_cima = MotorFalso(self.peca_motor_de_cima, ["LiquidFuel"], active=False)
        self.engines = [self.motor, self.motor_de_cima]
        self.all = [self.tanque, self.peca_motor, self.tanque_mono, self.carga, self.peca_motor_de_cima]
        self.control_surfaces = [SuperficieFalsa(), SuperficieFalsa(roll=False)]


class ControleFalso:
    def __init__(self, jogo):
        self.jogo = jogo
        self.sas = True
        self.rcs = False
        self.throttle = 0.0
        self.nodes = []

    def add_node(self, ut, prograde=0.0, normal=0.0, radial=0.0):
        if self.jogo.nao_cria_no:
            raise RuntimeError(SEM_CONICAS)
        no = NoFalso(self.jogo, ut, prograde, normal, radial)
        self.nodes.append(no)
        self.jogo.nos_criados.append(no)
        return no


class PilotoFalso:
    def __init__(self):
        self.reference_frame = None
        self.engajado = False
        self.quebrado = False
        self.servidor_antigo = False
        self.target_roll = 0.0
        self.target_direction = None

    @property
    def engaged(self):
        return self.engajado

    @engaged.setter
    def engaged(self, valor):
        if self.quebrado:
            raise RuntimeError("a nave não existe mais")
        if self.servidor_antigo:
            raise RuntimeError('Procedure "AutoPilot_set_Engaged" not found, in service "SpaceCenter"')
        self.engajado = valor


class VooFalso:
    def __init__(self, jogo, estado):
        self.jogo = jogo
        self.estado = estado

    @property
    def velocity(self):
        return self.jogo.eixos(self.estado()[1])

    @property
    def normal(self):
        r, v = self.estado()
        return self.jogo.eixos(unit(cruz(r, v)))


class NaveFalsa:
    name = "AEAS - SmalLifter"

    def __init__(self, jogo):
        self.jogo = jogo
        self.orbit = types.SimpleNamespace(body=jogo.corpo)
        self.surface_reference_frame = SUP
        self.control = ControleFalso(jogo)
        self.auto_pilot = PilotoFalso()
        self.parts = PartesFalsas(jogo)

    def position(self, referencia):
        return self.jogo.eixos(self.jogo.sim.r)

    def direction(self, referencia):
        return self.jogo.eixos(self.jogo.sim.nariz)

    def flight(self, referencia=None):
        sim = self.jogo.sim
        return VooFalso(self.jogo, lambda: (sim.r, sim.v))

    def velocity(self, referencia):
        return self.jogo.eixos(self.jogo.sim.v)

    @property
    def mass(self):
        return self.jogo.sim.massa

    @property
    def available_thrust(self):
        sim = self.jogo.sim
        return sim.empuxo if sim.combustivel > 0.0 else 0.0

    @property
    def specific_impulse(self):
        sim = self.jogo.sim
        return sim.isp if sim.combustivel > 0.0 else 0.0


class AlvoFalso:
    def __init__(self, jogo, nome="Estação um"):
        self.jogo = jogo
        self.name = nome
        self.orbit = types.SimpleNamespace(body=jogo.corpo)
        self.destruido = False

    def _estado(self):
        if self.destruido:
            raise RuntimeError("o objeto não existe mais")
        alvo = self.jogo.sim.alvo()
        return alvo.r, alvo.v

    def position(self, referencia):
        return self.jogo.eixos(self._estado()[0])

    def flight(self, referencia=None):
        return VooFalso(self.jogo, self._estado)


class CorpoFalso:
    name = "Kerbin"
    gravitational_parameter = KERBIN.mu
    equatorial_radius = KERBIN.raio
    has_atmosphere = True
    atmosphere_depth = KERBIN.topo
    sphere_of_influence = KERBIN.soi
    non_rotating_reference_frame = NR


class CentroFalso:
    def __init__(self, jogo):
        self.jogo = jogo
        self.target_vessel = None
        self.target_body = None
        self.warp_proibido = False
        self.warps = []

    @property
    def ut(self):
        return self.jogo.sim.t

    @property
    def active_vessel(self):
        return self.jogo.nave

    def transform_direction(self, direcao, de, para):
        assert de == SUP and para == NR and tuple(direcao) == (0.0, 0.0, 1.0)
        leste = unit(cruz(POLO, self.jogo.sim.r))
        if self.jogo.leste_errado:
            leste = esc(-1.0, leste)
        return self.jogo.eixos(leste)

    def warp_to(self, ut):
        if self.warp_proibido:
            raise RuntimeError("não dá para acelerar o tempo agora")
        self.warps.append(ut)
        self.jogo.sim.executar(Comando(0.0, None, acelerar_ate=ut))


class JogoFalso:
    """Um KSP de mentira em volta de uma NaveOrbital, com os eixos canhotos do kRPC (z trocado)."""

    def __init__(self, nave=HOJE_NAVE, alvo=HOJE_ALVO, canhoto=True, leste_errado=False, combustivel=COMBUSTIVEL_MODULO):
        self.sim = montar(nave, alvo, combustivel)
        self.canhoto = canhoto
        self.leste_errado = leste_errado
        self.fluxos = []
        self.procedimentos = []
        self.nos_criados = []
        self.nao_cria_no = False
        self.fechada = False
        self._types = types.SimpleNamespace(class_type=lambda servico, classe: (servico, classe))
        self.corpo = CorpoFalso()
        self.space_center = CentroFalso(self)
        self.nave = NaveFalsa(self)
        self.alvo = AlvoFalso(self)
        self.space_center.target_vessel = self.alvo

    def eixos(self, vetor):
        if self.canhoto:
            return (vetor[0], vetor[1], -vetor[2])
        return tuple(vetor)

    def add_stream(self, funcao, *argumentos):
        fluxo = FluxoFalso(funcao, argumentos)
        self.fluxos.append(fluxo)
        return fluxo

    def close(self):
        self.fechada = True

    def _invoke(self, servico, procedimento, argumentos, nomes, tipos, retorno):
        piloto = argumentos[0]
        if piloto.quebrado:
            raise RuntimeError("a nave não existe mais")
        self.procedimentos.append((servico, procedimento, tipos[0]))
        piloto.engajado = procedimento == "AutoPilot_Engage"

    def avancar(self, dt):
        controle = self.nave.control
        direcao = self.nave.auto_pilot.target_direction
        self.sim.executar(Comando(controle.throttle, None if direcao is None else self.eixos(direcao)))
        self.sim.avancar(dt)


@contextlib.contextmanager
def sem_espera():
    """Tira as esperas de tempo real e o terminal interativo, e guarda o que o script imprime."""
    with contextlib.ExitStack() as pilha:
        pilha.enter_context(mock.patch.object(rendezvous.time, "sleep"))
        pilha.enter_context(mock.patch.object(rendezvous, "INTERVALO_COMBUSTIVEL", 0.0))
        pilha.enter_context(mock.patch.object(sys, "stdin", io.StringIO()))
        saida = pilha.enter_context(contextlib.redirect_stdout(io.StringIO()))
        yield saida


def com_fisica(jogo, depois=None):
    """Faz cada NaveKrpc.executar andar o jogo falso por INTERVALO s, como o jogo de verdade faria."""
    original = rendezvous.NaveKrpc.executar

    def executar(fonte, comando):
        original(fonte, comando)
        jogo.avancar(rendezvous.INTERVALO)
        if depois is not None:
            depois()

    return mock.patch.object(rendezvous.NaveKrpc, "executar", executar)


def argumentos(**extras):
    base = dict(distancia=D_FINAL, voltas_max=6, so_planejar=False)
    base.update(extras)
    return argparse.Namespace(**base)


class TestNaveKrpc(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(rendezvous, "INTERVALO_COMBUSTIVEL", 0.0)
        patch.start()
        self.addCleanup(patch.stop)

    def criar(self, **extras):
        jogo = JogoFalso(**extras)
        return jogo, rendezvous.NaveKrpc(jogo, jogo.nave, jogo.corpo, rendezvous.planeta_do_jogo(jogo.corpo))

    def test_planeta_do_jogo(self):
        planeta = rendezvous.planeta_do_jogo(CorpoFalso())
        self.assertEqual(planeta, KERBIN)
        self.assertEqual(rendezvous.planeta_do_jogo(types.SimpleNamespace(
            name="Mun", gravitational_parameter=MUN.mu, equatorial_radius=MUN.raio, has_atmosphere=False,
            atmosphere_depth=0.0, sphere_of_influence=MUN.soi,
        )), MUN)

    def test_calibracao_do_z_e_leitura_igual_a_da_nave_simulada(self):
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo, fonte = self.criar(canhoto=canhoto)
                jogo.sim.avancar(3.0)
                l = fonte.ler()
                esperada = jogo.sim.leitura()
                self.assertEqual(fonte._sinal_z, -1.0 if canhoto else 1.0)
                for campo in ("r", "v", "nariz"):
                    self.assertLess(norma(sub(getattr(l, campo), getattr(esperada, campo))), 1e-6, campo)
                for campo in ("r", "v"):
                    self.assertLess(norma(sub(getattr(l.alvo, campo), getattr(esperada.alvo, campo))), 1e-6, campo)
                for campo in ("t", "massa", "empuxo", "isp"):
                    self.assertAlmostEqual(getattr(l, campo), getattr(esperada, campo), places=6, msg=campo)
                self.assertEqual(l.alvo.t, l.t)

    def test_leste_errado_levanta_erro_claro(self):
        jogo = JogoFalso(leste_errado=True)
        with self.assertRaises(rendezvous.ReferencialErrado) as erro:
            rendezvous.NaveKrpc(jogo, jogo.nave, jogo.corpo, KERBIN)
        self.assertIn("leste", str(erro.exception))

    def test_nave_sem_velocidade_nao_calibra(self):
        jogo = JogoFalso()
        jogo.sim.v = (0.0, 0.0, 0.0)
        with self.assertRaises(rendezvous.ReferencialErrado):
            rendezvous.NaveKrpc(jogo, jogo.nave, jogo.corpo, KERBIN)

    def test_combustivel_e_dos_tanques_do_motor_aceso(self):
        jogo, fonte = self.criar()
        partes = jogo.nave.parts
        self.assertAlmostEqual(fonte.ler().combustivel, COMBUSTIVEL_MODULO)
        jogo.sim.combustivel = 1_500.0
        self.assertAlmostEqual(fonte.ler().combustivel, 1_500.0)
        partes.motor.active = False
        partes.motor_de_cima.active = True
        self.assertAlmostEqual(fonte.ler().combustivel, 600.0)
        partes.motor_de_cima.active = False
        self.assertEqual(fonte.ler().combustivel, 0.0)

    def test_combustivel_e_relido_so_a_cada_intervalo(self):
        with mock.patch.object(rendezvous, "INTERVALO_COMBUSTIVEL", 3_600.0):
            jogo, fonte = self.criar()
            primeiro = fonte.ler().combustivel
            jogo.sim.combustivel = 10.0
            self.assertEqual(fonte.ler().combustivel, primeiro)

    def test_sem_alvo_e_alvo_em_outro_planeta_e_alvo_que_nao_e_nave(self):
        jogo, fonte = self.criar()
        self.assertIsNotNone(fonte.ler().alvo)
        self.assertEqual(fonte.nome_alvo, "Estação um")
        self.assertIsNone(fonte.problema_alvo)

        jogo = JogoFalso()
        jogo.space_center.target_vessel = None
        fonte = rendezvous.NaveKrpc(jogo, jogo.nave, jogo.corpo, KERBIN)
        self.assertIsNone(fonte.ler().alvo)
        self.assertIn("nenhuma nave", fonte.problema_alvo)

        jogo.space_center.target_body = types.SimpleNamespace(name="Mun")
        fonte = rendezvous.NaveKrpc(jogo, jogo.nave, jogo.corpo, KERBIN)
        self.assertIsNone(fonte.ler().alvo)
        self.assertIn("Mun", fonte.problema_alvo)
        self.assertIn("não uma nave", fonte.problema_alvo)

        jogo = JogoFalso()
        jogo.alvo.orbit = types.SimpleNamespace(body=object())
        fonte = rendezvous.NaveKrpc(jogo, jogo.nave, jogo.corpo, KERBIN)
        self.assertIsNone(fonte.ler().alvo)
        self.assertIn("não orbita Kerbin", fonte.problema_alvo)
        self.assertEqual(fonte.nome_alvo, "Estação um")

    def test_alvo_que_some_no_meio_vem_sem_alvo(self):
        jogo, fonte = self.criar()
        self.assertIsNotNone(fonte.ler().alvo)
        jogo.alvo.destruido = True
        l = fonte.ler()
        self.assertIsNone(l.alvo)
        self.assertGreater(l.massa, 0.0)

    def test_executar_liga_o_piloto_automatico_e_desliga_o_sas(self):
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo, fonte = self.criar(canhoto=canhoto)
                nave = jogo.nave
                fonte.ler()
                fonte.executar(Comando(0.6, (1.0, 2.0, 3.0)))
                self.assertFalse(nave.control.sas)
                self.assertTrue(nave.control.rcs)
                self.assertTrue(math.isnan(nave.auto_pilot.target_roll))
                self.assertEqual(nave.auto_pilot.reference_frame, NR)
                for superficie in nave.parts.control_surfaces:
                    self.assertEqual((superficie.pitch_enabled, superficie.yaw_enabled, superficie.roll_enabled), (False,) * 3)
                self.assertTrue(nave.auto_pilot.engajado)
                self.assertEqual(nave.control.throttle, 0.6)
                enviada = nave.auto_pilot.target_direction
                self.assertLess(norma(sub(jogo.eixos(enviada), unit((1.0, 2.0, 3.0)))), 1e-9)
                self.assertEqual(enviada[2], -unit((1.0, 2.0, 3.0))[2] if canhoto else unit((1.0, 2.0, 3.0))[2])
                self.assertEqual(jogo.procedimentos, [])

    def test_comando_sem_direcao_nao_mexe_na_direcao(self):
        jogo, fonte = self.criar()
        fonte.ler()
        fonte.executar(Comando(0.0, None))
        self.assertIsNone(jogo.nave.auto_pilot.target_direction)
        fonte.executar(Comando(0.0, (0.0, 0.0, 0.0)))
        self.assertIsNone(jogo.nave.auto_pilot.target_direction)

    def test_piloto_automatico_com_o_servidor_0_5(self):
        jogo, fonte = self.criar()
        jogo.nave.auto_pilot.servidor_antigo = True
        fonte.ler()
        fonte.executar(Comando(0.0, (1.0, 0.0, 0.0)))
        self.assertTrue(jogo.nave.auto_pilot.engajado)
        fonte.liberar()
        self.assertFalse(jogo.nave.auto_pilot.engajado)
        tipo = ("SpaceCenter", "AutoPilot")
        self.assertEqual(
            jogo.procedimentos,
            [("SpaceCenter", "AutoPilot_Engage", tipo), ("SpaceCenter", "AutoPilot_Disengage", tipo)],
        )

    def test_time_warp_bloqueia_ate_o_tempo_pedido(self):
        jogo, fonte = self.criar()
        fonte.ler()
        fonte.executar(Comando(0.0, (1.0, 0.0, 0.0), acelerar_ate=UT_HOJE + 500.0))
        self.assertEqual(jogo.space_center.warps, [UT_HOJE + 500.0])
        self.assertAlmostEqual(jogo.sim.t, UT_HOJE + 500.0)
        fonte.executar(Comando(0.0, (1.0, 0.0, 0.0), acelerar_ate=UT_HOJE + 100.0))
        self.assertEqual(jogo.space_center.warps, [UT_HOJE + 500.0])

    def test_sem_warp_o_aviso_sai_uma_vez_so(self):
        jogo, fonte = self.criar()
        jogo.space_center.warp_proibido = True
        fonte.ler()
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            fonte.executar(Comando(acelerar_ate=UT_HOJE + 500.0))
            fonte.executar(Comando(acelerar_ate=UT_HOJE + 600.0))
        self.assertEqual(saida.getvalue().count("AVISO"), 1)
        self.assertEqual(jogo.sim.t, UT_HOJE)

    def test_componentes_do_no(self):
        dv = (3.0, -2.0, 5.0)
        for estado in (HOJE_NAVE, circular(KERBIN, 100_000.0, 30.0)):
            with self.subTest(r=norma(estado.r)):
                for t in (estado.t, estado.t + 1_234.0, estado.t - 500.0):
                    pro, nor, rad = rendezvous.componentes_do_no(MU, estado, t, dv)
                    r, v = propagar(MU, estado.r, estado.v, t - estado.t)
                    p = unit(v)
                    n = unit(cruz(r, v))
                    fora = unit(sub(r, esc(ponto(r, p), p)))
                    montado = soma(soma(esc(pro, p), esc(nor, n)), esc(rad, fora))
                    self.assertLess(norma(sub(montado, dv)), 1e-9)
        pro, nor, rad = rendezvous.componentes_do_no(MU, HOJE_NAVE, UT_HOJE, esc(10.0, unit(HOJE_NAVE.r)))
        self.assertGreater(rad, 5.0)

    def test_no_criado_com_os_componentes_certos_e_recriado_so_se_mudou(self):
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo, fonte = self.criar(canhoto=canhoto)
                controle = jogo.nave.control
                fonte.ler()
                t1, dv1 = UT_HOJE + 600.0, (3.0, -2.0, 5.0)
                fonte.executar(Comando(0.0, None, no=(t1, dv1), no_mudou=True))
                self.assertEqual(len(controle.nodes), 1)
                no = controle.nodes[0]
                self.assertEqual(no.ut, t1)
                self.assertLess(norma(sub(jogo.eixos(no.burn_vector(NR)), dv1)), 1e-9)
                self.assertLess(angulo(fonte._corrigir(no.burn_vector(NR)), dv1), 1e-4)
                for _ in range(3):
                    fonte.executar(Comando(0.0, None, no=(t1, dv1), no_mudou=False))
                self.assertEqual(len(jogo.nos_criados), 1)
                t2, dv2 = UT_HOJE + 900.0, (-1.0, 0.5, 2.0)
                fonte.executar(Comando(0.0, None, no=(t2, dv2), no_mudou=True))
                self.assertEqual(len(jogo.nos_criados), 2)
                self.assertTrue(no.removido)
                self.assertEqual(controle.nodes, [jogo.nos_criados[1]])
                self.assertLess(norma(sub(jogo.eixos(controle.nodes[0].burn_vector(NR)), dv2)), 1e-9)
                fonte.executar(Comando(0.0, None, no=None, no_mudou=True))
                self.assertEqual(controle.nodes, [])

    def test_no_no_passado_vai_para_agora(self):
        jogo, fonte = self.criar()
        fonte.ler()
        fonte.executar(Comando(0.0, None, no=(UT_HOJE - 50.0, (1.0, 1.0, 1.0)), no_mudou=True))
        self.assertEqual(jogo.nos_criados[0].ut, UT_HOJE)

    def test_nos_do_piloto_ficam_e_o_do_script_some(self):
        jogo, fonte = self.criar()
        controle = jogo.nave.control
        do_piloto = controle.add_node(UT_HOJE + 5_000.0, prograde=10.0)
        fonte.ler()
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            fonte.executar(Comando(0.0, (1.0, 0.0, 0.0), no=(UT_HOJE + 600.0, (3.0, 0.0, 0.0)), no_mudou=True))
            fonte.executar(Comando(0.0, (1.0, 0.0, 0.0), no=(UT_HOJE + 700.0, (4.0, 0.0, 0.0)), no_mudou=True))
        self.assertEqual(saida.getvalue().count("AVISO: já há 1 nó"), 1)
        self.assertEqual(len(controle.nodes), 2)
        fonte.liberar()
        self.assertEqual(controle.nodes, [do_piloto])
        self.assertFalse(do_piloto.removido)

    def test_nao_dar_para_criar_o_no_avisa_uma_vez_e_segue(self):
        jogo, fonte = self.criar()
        jogo.nao_cria_no = True
        fonte.ler()
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            fonte.executar(Comando(0.4, (1.0, 0.0, 0.0), no=(UT_HOJE + 600.0, (3.0, 0.0, 0.0)), no_mudou=True))
            fonte.executar(Comando(0.4, (1.0, 0.0, 0.0), no=(UT_HOJE + 700.0, (3.0, 0.0, 0.0)), no_mudou=True))
        self.assertEqual(saida.getvalue().count("não consegui criar o nó"), 1)
        self.assertIn(SEM_CONICAS, saida.getvalue())
        self.assertEqual(jogo.nave.control.throttle, 0.4)
        self.assertEqual(jogo.nave.control.nodes, [])

    def test_liberar_deixa_tudo_como_estava(self):
        for antes in (False, True):
            with self.subTest(rcs_antes=antes):
                jogo, fonte = self.criar()
                controle = jogo.nave.control
                controle.rcs = antes
                fonte.ler()
                fonte.executar(Comando(0.8, (1.0, 0.0, 0.0), no=(UT_HOJE + 600.0, (3.0, 0.0, 0.0)), no_mudou=True))
                self.assertTrue(controle.rcs)
                fonte.liberar()
                self.assertEqual(controle.throttle, 0.0)
                self.assertTrue(controle.sas)
                self.assertEqual(controle.rcs, antes)
                self.assertFalse(jogo.nave.auto_pilot.engajado)
                self.assertEqual(controle.nodes, [])
                self.assertTrue(all(f.removido for f in jogo.fluxos))
                estados = [(s.pitch_enabled, s.yaw_enabled, s.roll_enabled) for s in jogo.nave.parts.control_surfaces]
                self.assertEqual(estados, [(True, True, True), (True, True, False)])

    def test_liberar_faz_cada_passo_por_si(self):
        jogo, fonte = self.criar()
        fonte.ler()
        fonte.executar(Comando(0.8, (1.0, 0.0, 0.0), no=(UT_HOJE + 600.0, (3.0, 0.0, 0.0)), no_mudou=True))
        jogo.nave.auto_pilot.quebrado = True
        fonte.liberar()
        self.assertEqual(jogo.nave.control.throttle, 0.0)
        self.assertTrue(jogo.nave.control.sas)
        self.assertEqual(jogo.nave.control.nodes, [])
        self.assertTrue(all(f.removido for f in jogo.fluxos))

    def test_liberar_sem_ter_assumido_o_controle_so_apaga_o_no_e_as_streams(self):
        jogo, fonte = self.criar()
        controle = jogo.nave.control
        controle.sas = False
        controle.throttle = 0.3
        fonte.ler()
        fonte.mostrar_no(Comando(no=(UT_HOJE + 600.0, (3.0, 0.0, 0.0)), no_mudou=True))
        self.assertEqual(len(controle.nodes), 1)
        fonte.liberar()
        self.assertEqual(controle.nodes, [])
        self.assertTrue(all(f.removido for f in jogo.fluxos))
        self.assertFalse(controle.sas)
        self.assertEqual(controle.throttle, 0.3)
        self.assertEqual(jogo.procedimentos, [])

    def test_comparar_no_com_o_burn_vector_e_a_previsao_do_jogo(self):
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo, fonte = self.criar(canhoto=canhoto)
                tr = planejar_transferencia(KERBIN, HOJE_NAVE, HOJE_ALVO, UT_HOJE, 6)
                self.assertEqual(fonte.comparar_no(tr.dv1), {})
                fonte.ler()
                fonte.mostrar_no(Comando(no=(tr.t1, tr.dv1), no_mudou=True))
                jogo_diz = fonte.comparar_no(tr.dv1)
                self.assertLess(jogo_diz["angulo"], 1e-4)
                self.assertLess(jogo_diz["distancia"], 2_000.0)
                self.assertTrue(UT_HOJE < jogo_diz["t"] < UT_HOJE + 40_000.0)
                errado = esc(1.0, rotacionar(tr.dv1, unit(cruz(tr.dv1, POLO)), math.radians(2.0)))
                self.assertAlmostEqual(fonte.comparar_no(errado)["angulo"], 2.0, places=3)


class TestTextos(unittest.TestCase):
    def test_duracao(self):
        textos = [rendezvous._texto_duracao(s) for s in (42.0, 423.0, 12_240.0, -61.0)]
        self.assertEqual(textos, ["42 s", "7 min 03 s", "3 h 24 min", "1 min 01 s"])
        self.assertEqual(rendezvous._texto_t(30.0), "T-30 s")
        self.assertEqual(rendezvous._texto_t(-5.4), "T+5 s")

    def test_distancia(self):
        self.assertEqual(rendezvous._texto_distancia(285.4), "285 m")
        self.assertEqual(rendezvous._texto_distancia(585_500.0), "585.5 km")

    def test_plano_e_linha_de_status(self):
        nave = montar(HOJE_NAVE, HOJE_ALVO)
        l = nave.leitura()
        g = Guiagem(KERBIN, D_FINAL, 6)
        g.passo(l)
        plano = rendezvous.linhas_do_plano(l, g)
        self.assertEqual(len(plano), 3)
        self.assertRegex(plano[0], r"transferência: [0-9.]+ m/s em T-[0-9]+ s")
        self.assertRegex(plano[1], r"[0-9.]+ voltas de transferência, em UT [0-9]+ s .*velocidade relativa [0-9.]+ m/s")
        self.assertRegex(plano[2], r"previsto: [0-9.]+ m/s .* disponível: [0-9]+ m/s")
        linha = rendezvous.status(l, g)
        self.assertRegex(linha, r"^TRANSFERENCIA +dist +585\.\d km +vrel +\d+\.\d\d m/s +proxima T-\d+ s [0-9.]+ m/s +gasto +0\.0 m/s +motor +0%$")
        sem_alvo = nave.leitura()
        sem_alvo.alvo = None
        self.assertIn("dist      ---", rendezvous.status(sem_alvo, g))

    def test_texto_do_aviso(self):
        fonte = types.SimpleNamespace(problema_alvo="nenhuma nave escolhida como alvo no jogo.")
        self.assertEqual(rendezvous.texto_do_aviso("ALVO", fonte), "nenhuma nave escolhida como alvo no jogo.")
        fonte.problema_alvo = None
        self.assertIn("alvo sumiu", rendezvous.texto_do_aviso("ALVO", fonte))
        for aviso in ("ORBITA", "TRANSFERENCIA", "COMBUSTIVEL"):
            self.assertIn(aviso, rendezvous.PRIORIDADE_AVISOS)
            self.assertTrue(rendezvous.texto_do_aviso(aviso, fonte))
        self.assertIn("desistiu", rendezvous.texto_do_aviso(None, fonte))


class TestEncontrar(unittest.TestCase):
    def voar(self, jogo, **extras):
        with sem_espera() as saida:
            with com_fisica(jogo):
                codigo = rendezvous.encontrar(jogo, argumentos(**extras))
        return codigo, saida.getvalue()

    def conferir_liberada(self, jogo):
        controle = jogo.nave.control
        self.assertEqual(controle.throttle, 0.0)
        self.assertTrue(controle.sas)
        self.assertFalse(jogo.nave.auto_pilot.engajado)
        self.assertTrue(all(f.removido for f in jogo.fluxos))

    def test_voo_completo_pelo_krpc_nos_dois_sentidos_do_referencial(self):
        tr = planejar_transferencia(KERBIN, HOJE_NAVE, HOJE_ALVO, UT_HOJE, 6)
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo = JogoFalso(canhoto=canhoto)
                codigo, texto = self.voar(jogo)
                self.assertEqual(codigo, rendezvous.CHEGOU, texto)
                l = jogo.sim.leitura()
                self.assertLess(norma(sub(l.alvo.r, l.r)), D_FINAL + 50.0)
                self.assertLess(norma(sub(l.v, l.alvo.v)), 0.3)
                self.assertLess(MASSA_MODULO - jogo.sim.massa, 50.0 / (ISP_MODULO * G0) * MASSA_MODULO)
                self.assertTrue(jogo.space_center.warps)
                self.conferir_liberada(jogo)
                self.assertEqual(jogo.nave.control.nodes, [])
                self.assertGreaterEqual(len(jogo.nos_criados), 3)
                self.assertTrue(all(no.removido for no in jogo.nos_criados))
                primeiro = jogo.nos_criados[0]
                self.assertAlmostEqual(primeiro.ut, tr.t1, places=3)
                self.assertLess(norma(sub(jogo.eixos(primeiro.burn_vector(NR)), tr.dv1)), 1e-6)
                self.assertIn("Queima de transferência", texto)
                for fase in ("TRANSFERENCIA", "CORRECAO", "VELOCIDADE", "APROXIMA", "ENCONTRO"):
                    self.assertIn(f"--> {fase}", texto)
                self.assertRegex(texto, r"Encontro: a \d+ m do alvo, velocidade relativa [0-9.]+ m/s")

    def test_sem_alvo_nao_comeca(self):
        jogo = JogoFalso()
        jogo.space_center.target_vessel = None
        codigo, texto = self.voar(jogo)
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertIn("AVISO: nenhuma nave escolhida como alvo", texto)
        self.assertIn("Não chegou: nenhuma nave escolhida", texto)
        self.assertEqual(jogo.nos_criados, [])
        self.assertEqual(jogo.procedimentos, [])
        self.assertEqual(jogo.sim.t, UT_HOJE)
        self.conferir_liberada(jogo)

    def test_alvo_em_outro_planeta_nao_comeca(self):
        jogo = JogoFalso()
        jogo.alvo.orbit = types.SimpleNamespace(body=object())
        jogo.alvo.name = "Estação Duna"
        codigo, texto = self.voar(jogo)
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertIn("Estação Duna não orbita Kerbin", texto)
        self.assertEqual(jogo.nos_criados, [])
        self.assertEqual(jogo.sim.t, UT_HOJE)

    def test_aviso_alvo_vem_da_guiagem(self):
        jogo = JogoFalso()
        jogo.space_center.target_vessel = None
        fonte = rendezvous.NaveKrpc(jogo, jogo.nave, jogo.corpo, KERBIN)
        g = Guiagem(KERBIN, D_FINAL, 6)
        g.passo(fonte.ler())
        self.assertEqual((g.fase, g.aviso), (FALHA, "ALVO"))

    def test_alvo_que_some_no_meio_do_voo_e_falha(self):
        jogo = JogoFalso()
        chamadas = []

        def derrubar():
            chamadas.append(1)
            if len(chamadas) == 5:
                jogo.alvo.destruido = True

        with sem_espera() as saida:
            with com_fisica(jogo, derrubar):
                codigo = rendezvous.encontrar(jogo, argumentos())
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertIn("Não chegou: sem alvo válido", saida.getvalue())
        self.conferir_liberada(jogo)
        self.assertEqual(jogo.nave.control.nodes, [])

    def test_pouco_combustivel_falha_antes_de_queimar(self):
        jogo = JogoFalso(combustivel=100.0)
        codigo, texto = self.voar(jogo)
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertIn("combustível insuficiente", texto)
        self.assertEqual(jogo.nos_criados, [])
        self.assertEqual(jogo.sim.massa, MASSA_MODULO)

    def test_ctrl_c_no_warp_libera_a_nave(self):
        jogo = JogoFalso()
        do_piloto = jogo.nave.control.add_node(UT_HOJE + 9_000.0, prograde=5.0)

        def interromper(ut):
            raise KeyboardInterrupt

        jogo.space_center.warp_to = interromper
        with sem_espera() as saida:
            with com_fisica(jogo):
                with self.assertRaises(KeyboardInterrupt):
                    rendezvous.encontrar(jogo, argumentos())
        self.assertEqual(len(jogo.nos_criados), 2)
        self.assertTrue(jogo.nave.auto_pilot.target_direction is not None)
        self.conferir_liberada(jogo)
        self.assertEqual(jogo.nave.control.nodes, [do_piloto])
        self.assertFalse(do_piloto.removido)
        self.assertIn("AVISO: já há 1 nó", saida.getvalue())

    def test_ctrl_c_no_laco_libera_a_nave(self):
        jogo = JogoFalso()
        chamadas = []

        def interromper():
            chamadas.append(1)
            if len(chamadas) == 3:
                raise KeyboardInterrupt

        with sem_espera():
            with com_fisica(jogo, interromper):
                with self.assertRaises(KeyboardInterrupt):
                    rendezvous.encontrar(jogo, argumentos())
        self.conferir_liberada(jogo)
        self.assertEqual(jogo.nave.control.nodes, [])
        self.assertTrue(jogo.nos_criados)

    def test_so_planejar_cria_o_no_imprime_o_plano_e_nao_liga_o_piloto(self):
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo = JogoFalso(canhoto=canhoto)
                controle = jogo.nave.control
                controle.sas = False
                esperas = []
                texto_pedido = []

                def entrar(mensagem):
                    texto_pedido.append(mensagem)
                    esperas.append(list(controle.nodes))
                    return ""

                with sem_espera() as saida:
                    with mock.patch.object(sys, "stdin", types.SimpleNamespace(isatty=lambda: True)):
                        with mock.patch("builtins.input", side_effect=entrar):
                            codigo = rendezvous.encontrar(jogo, argumentos(so_planejar=True))
                texto = saida.getvalue()
                self.assertEqual(codigo, rendezvous.CHEGOU, texto)
                self.assertEqual(len(jogo.nos_criados), 1)
                self.assertEqual(esperas, [[jogo.nos_criados[0]]])
                self.assertIn("Enter para apagar o nó e sair", texto_pedido[0])
                self.assertEqual(controle.nodes, [])
                self.assertTrue(jogo.nos_criados[0].removido)
                self.assertFalse(jogo.nave.auto_pilot.engajado)
                self.assertEqual(jogo.procedimentos, [])
                self.assertIsNone(jogo.nave.auto_pilot.target_direction)
                self.assertFalse(controle.sas)
                self.assertFalse(controle.rcs)
                self.assertEqual(controle.throttle, 0.0)
                self.assertEqual(jogo.space_center.warps, [])
                self.assertEqual(jogo.sim.t, UT_HOJE)
                self.assertTrue(all(f.removido for f in jogo.fluxos))
                self.assertIn("Queima de transferência", texto)
                self.assertRegex(texto, r"Menor distância pela nossa conta: \d+ m")
                self.assertRegex(texto, r"Menor distância que o kRPC prevê com o nó: \d+ m")
                angulo_jogo = float(re.search(r"nosso dv1: ([0-9.]+)°", texto).group(1))
                self.assertLess(angulo_jogo, 0.1)
                self.assertNotIn("AVISO", texto)

    def test_so_planejar_sem_terminal_apaga_logo(self):
        jogo = JogoFalso()
        with sem_espera() as saida:
            with mock.patch("builtins.input", side_effect=AssertionError("não devia esperar")):
                codigo = rendezvous.encontrar(jogo, argumentos(so_planejar=True))
        self.assertEqual(codigo, rendezvous.CHEGOU)
        self.assertEqual(jogo.nave.control.nodes, [])
        self.assertEqual(len(jogo.nos_criados), 1)
        self.assertIn("Queima de transferência", saida.getvalue())

    def test_so_planejar_com_o_no_de_diferenca_grande_avisa(self):
        jogo = JogoFalso()
        original = NoFalso.burn_vector

        def torto(no, referencia):
            return rotacionar(original(no, referencia), (0.0, 1.0, 0.0), math.radians(3.0))

        with sem_espera() as saida:
            with mock.patch.object(NoFalso, "burn_vector", torto):
                codigo = rendezvous.encontrar(jogo, argumentos(so_planejar=True))
        self.assertEqual(codigo, rendezvous.CHEGOU)
        self.assertIn("AVISO: o nó do jogo difere do dv1", saida.getvalue())

    def test_so_planejar_sem_alvo_nao_cria_no(self):
        jogo = JogoFalso()
        jogo.space_center.target_vessel = None
        with sem_espera() as saida:
            codigo = rendezvous.encontrar(jogo, argumentos(so_planejar=True))
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertEqual(jogo.nos_criados, [])
        self.assertIn("Não chegou", saida.getvalue())
        self.assertFalse(jogo.nave.auto_pilot.engajado)

    def test_so_planejar_com_plano_diferente_mostra_o_no_do_plano(self):
        n_alvo = rotacionar(POLO, (1.0, 0.0, 0.0), math.radians(0.5))
        nave = circular(KERBIN, 158_000.0, 100.0)
        alvo = circular(KERBIN, 158_000.0, 150.0, normal=n_alvo)
        jogo = JogoFalso(nave, alvo)
        with sem_espera() as saida:
            codigo = rendezvous.encontrar(jogo, argumentos(so_planejar=True))
        self.assertEqual(codigo, rendezvous.CHEGOU)
        self.assertEqual(len(jogo.nos_criados), 1)
        self.assertIn("o primeiro nó é o do plano", saida.getvalue())
        self.assertFalse(jogo.nave.auto_pilot.engajado)

    def test_so_planejar_com_o_alvo_perto_nao_cria_no(self):
        graus = math.degrees(2_000.0 / (KERBIN.raio + 158_000.0))
        jogo = JogoFalso(circular(KERBIN, 158_000.0, 0.0), circular(KERBIN, 158_000.0, graus))
        with sem_espera() as saida:
            codigo = rendezvous.encontrar(jogo, argumentos(so_planejar=True))
        self.assertEqual(codigo, rendezvous.CHEGOU)
        self.assertEqual(jogo.nos_criados, [])
        self.assertIn("não há transferência", saida.getvalue())

    def test_eixos_errados_nao_comecam(self):
        jogo = JogoFalso(leste_errado=True)
        codigo, texto = self.voar(jogo)
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertIn("ERRO", texto)
        self.assertEqual(jogo.nos_criados, [])

    def test_distancia_pedida_vale_no_voo(self):
        jogo = JogoFalso()
        codigo, texto = self.voar(jogo, distancia=200.0)
        self.assertEqual(codigo, rendezvous.CHEGOU, texto)
        l = jogo.sim.leitura()
        self.assertAlmostEqual(norma(sub(l.alvo.r, l.r)), 200.0, delta=70.0)


class TestMain(unittest.TestCase):
    def rodar(self, *opcoes):
        with sem_espera() as saida:
            with mock.patch.object(sys, "argv", ["rendezvous.py", *opcoes]):
                codigo = rendezvous.main()
        return codigo, saida.getvalue()

    def test_demo_chega_perto_do_alvo(self):
        codigo, texto = self.rodar("--demo")
        self.assertEqual(codigo, rendezvous.CHEGOU, texto)
        self.assertIn("Demonstração", texto)
        for fase in ("TRANSFERENCIA", "CORRECAO", "VELOCIDADE", "APROXIMA", "ENCONTRO"):
            self.assertIn(f"--> {fase}", texto)
        self.assertRegex(texto, r"Encontro: a \d+ m do alvo, velocidade relativa [0-9.]+ m/s, Dv gasto [0-9.]+ m/s")
        self.assertRegex(texto, r"TRANSFERENCIA +dist +\d+\.\d km +vrel")
        distancia = float(re.search(r"Encontro: a (\d+) m", texto).group(1))
        self.assertLess(distancia, 150.0)

    def test_demo_com_distancia_diferente(self):
        codigo, texto = self.rodar("--demo", "--distancia", "200")
        self.assertEqual(codigo, rendezvous.CHEGOU)
        self.assertIn("distância final: 200 m", texto)
        distancia = float(re.search(r"Encontro: a (\d+) m", texto).group(1))
        self.assertTrue(150.0 < distancia < 250.0)

    def test_demo_so_planejar_nao_voa(self):
        codigo, texto = self.rodar("--demo", "--so-planejar")
        self.assertEqual(codigo, rendezvous.CHEGOU)
        self.assertIn("Queima de transferência", texto)
        self.assertIn("Menor distância pela nossa conta", texto)
        self.assertNotIn("kRPC", texto)
        self.assertNotIn("-->", texto)

    def test_ctrl_c_na_demo_devolve_130(self):
        with mock.patch.object(rendezvous, "encontrar_demo", side_effect=KeyboardInterrupt):
            codigo, texto = self.rodar("--demo")
        self.assertEqual(codigo, rendezvous.INTERROMPIDO)
        self.assertEqual(rendezvous.INTERROMPIDO, 130)

    def test_argumentos_do_krpc(self):
        jogo = JogoFalso()
        chamadas = []

        def conectar_krpc(address, *dispositivos, esperar=True):
            chamadas.append((address, dispositivos, esperar))
            return jogo

        falsa = types.SimpleNamespace(conectar_krpc=conectar_krpc)
        recebidos = []
        with mock.patch.dict(sys.modules, {"ponte": falsa}):
            with mock.patch.object(rendezvous, "encontrar", lambda conn, args: recebidos.append(args) or 0):
                codigo, _ = self.rodar("10.0.0.5", "--distancia", "250", "--voltas-max", "9", "--so-planejar")
        self.assertEqual(codigo, 0)
        self.assertEqual(chamadas, [("10.0.0.5", (), False)])
        self.assertEqual((recebidos[0].distancia, recebidos[0].voltas_max, recebidos[0].so_planejar), (250.0, 9, True))
        self.assertTrue(jogo.fechada)
        with mock.patch.dict(sys.modules, {"ponte": falsa}):
            with mock.patch.object(rendezvous, "encontrar", lambda conn, args: recebidos.append(args) or 0):
                self.rodar()
        padrao = recebidos[1]
        self.assertEqual((padrao.address, padrao.distancia, padrao.voltas_max, padrao.so_planejar, padrao.demo),
                         ("127.0.0.1", 100.0, 6, False, False))

    def test_krpc_voa_ate_o_encontro_e_fecha_a_conexao(self):
        jogo = JogoFalso()
        falsa = types.SimpleNamespace(conectar_krpc=lambda address, *d, esperar=True: jogo)
        with mock.patch.dict(sys.modules, {"ponte": falsa}):
            with com_fisica(jogo):
                codigo, texto = self.rodar()
        self.assertEqual(codigo, rendezvous.CHEGOU, texto)
        self.assertTrue(jogo.fechada)
        self.assertEqual(jogo.nave.control.nodes, [])
        self.assertTrue(jogo.nave.control.sas)

    def test_ctrl_c_no_krpc_devolve_130_e_libera(self):
        jogo = JogoFalso()
        falsa = types.SimpleNamespace(conectar_krpc=lambda address, *d, esperar=True: jogo)

        def interromper(ut):
            raise KeyboardInterrupt

        jogo.space_center.warp_to = interromper
        with mock.patch.dict(sys.modules, {"ponte": falsa}):
            with com_fisica(jogo):
                codigo, texto = self.rodar()
        self.assertEqual(codigo, rendezvous.INTERROMPIDO)
        self.assertIn("Interrompido", texto)
        self.assertTrue(jogo.fechada)
        self.assertEqual(jogo.nave.control.throttle, 0.0)
        self.assertTrue(jogo.nave.control.sas)
        self.assertFalse(jogo.nave.auto_pilot.engajado)
        self.assertEqual(jogo.nave.control.nodes, [])

    def test_nave_perdida_devolve_nao_chegou(self):
        jogo = JogoFalso()
        falsa = types.SimpleNamespace(conectar_krpc=lambda address, *d, esperar=True: jogo)
        with mock.patch.dict(sys.modules, {"ponte": falsa}):
            with mock.patch.object(Guiagem, "passo", side_effect=RuntimeError("a nave explodiu")):
                codigo, texto = self.rodar()
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertIn("Perdi a nave", texto)
        self.assertTrue(jogo.fechada)
        self.assertTrue(all(f.removido for f in jogo.fluxos))

    def test_sem_nave_ativa(self):
        jogo = JogoFalso()

        class SemNave(CentroFalso):
            @property
            def active_vessel(self):
                raise RuntimeError("sem nave ativa")

        jogo.space_center = SemNave(jogo)
        with sem_espera() as saida:
            codigo = rendezvous.encontrar(jogo, argumentos())
        self.assertEqual(codigo, rendezvous.NAO_CHEGOU)
        self.assertIn("Nenhuma nave ativa", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
