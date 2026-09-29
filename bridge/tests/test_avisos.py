"""Testes dos avisos de voo por voz (avisos.py), sem o KSP e sem som.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_avisos.py
    python bridge/tests/test_avisos.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import avisos
from avisos import FRASES, PES, Avisos, Voo
from mfd import Telemetria, voo_dos_avisos

PASSO = 0.05


def cruzeiro(**kwargs):
    valores = dict(radar=1000.0, vv=0.0, velocidade=120.0, rolagem=0.0, pressao=9000.0, no_ar=True, trem=False)
    valores.update(kwargs)
    return Voo(**valores)


def voar(a, inicio, duracao, voo_em):
    """Chama atualizar a cada PASSO; devolve as falas e os níveis de luz vistos."""
    falas, niveis = [], set()
    t = inicio
    while t < inicio + duracao - 1e-9:
        fala = a.atualizar(voo_em(t), t)
        if fala is not None:
            falas.append(fala)
        niveis.add(a.nivel)
        t += PASSO
    return falas, niveis


class TestAvisos(unittest.TestCase):
    def test_cruzeiro_alto_nao_avisa(self):
        a = Avisos()
        falas, niveis = voar(a, 0.0, 10.0, lambda t: cruzeiro())
        self.assertEqual(falas, [])
        self.assertEqual(niveis, {0})

    def test_no_chao_ou_fora_do_ar_nao_avisa(self):
        a = Avisos()
        falas, _ = voar(a, 0.0, 5.0, lambda t: cruzeiro(radar=5.0, vv=-30.0, no_ar=False))
        self.assertEqual(falas, [])
        falas, _ = voar(a, 5.0, 5.0, lambda t: cruzeiro(radar=100.0, vv=-30.0, pressao=100.0))
        self.assertEqual(falas, [])

    def test_sink_rate_e_depois_pull_up(self):
        a = Avisos()
        voar(a, 0.0, 1.0, lambda t: cruzeiro(radar=400.0))
        falas, niveis = voar(a, 1.0, 3.0, lambda t: cruzeiro(radar=400.0, vv=-20.0))
        self.assertIn("SINK_RATE", falas)
        self.assertEqual(niveis, {1})
        falas, niveis = voar(a, 4.0, 3.0, lambda t: cruzeiro(radar=300.0, vv=-30.0))
        self.assertIn("PULL_UP", falas)
        self.assertIn(2, niveis)

    def test_pouso_normal_so_faz_as_chamadas(self):
        a = Avisos()
        voar(a, 0.0, 1.0, lambda t: cruzeiro(radar=200.0, trem=True, vv=-3.0))

        def aproximacao(t):
            return cruzeiro(radar=max(1.0, 200.0 - 3.0 * (t - 1.0)), vv=-3.0, velocidade=60.0, trem=True)

        falas, niveis = voar(a, 1.0, 70.0, aproximacao)
        self.assertEqual(falas, [100, 50, 40, 30, 20, 10])
        self.assertEqual(niveis, {0})

    def test_ponte_aberta_no_ar_nao_e_decolagem(self):
        a = Avisos()
        falas, _ = voar(a, 0.0, 10.0, lambda t: cruzeiro(radar=150.0 - 5.0 * t, vv=-5.0, trem=True, velocidade=60.0))
        self.assertNotIn("DONT_SINK", falas)

    def test_chao_subindo_da_terrain_e_pull_up(self):
        a = Avisos()
        voar(a, 0.0, 1.0, lambda t: cruzeiro(radar=400.0, velocidade=200.0))
        falas, niveis = voar(a, 1.0, 5.0, lambda t: cruzeiro(radar=400.0 - 60.0 * (t - 1.0), velocidade=200.0))
        self.assertEqual(falas[0], "TERRAIN")
        self.assertIn("PULL_UP", falas)
        self.assertIn(2, niveis)

    def test_dont_sink_depois_da_decolagem(self):
        a = Avisos()
        voar(a, 0.0, 1.0, lambda t: cruzeiro(radar=1.0, no_ar=False, trem=True))
        voar(a, 1.0, 10.0, lambda t: cruzeiro(radar=1.0 + 10.0 * (t - 1.0), vv=10.0, trem=False))
        falas, _ = voar(a, 11.0, 4.0, lambda t: cruzeiro(radar=101.0 - 5.0 * (t - 11.0), vv=-5.0, trem=False))
        self.assertIn("DONT_SINK", falas)
        self.assertNotIn("TOO_LOW_GEAR", falas)

    def test_too_low_gear_e_too_low_terrain(self):
        a = Avisos()
        voar(a, 0.0, 1.0, lambda t: cruzeiro(radar=100.0))
        falas, _ = voar(a, 1.0, 4.0, lambda t: cruzeiro(radar=100.0, velocidade=70.0))
        self.assertIn("TOO_LOW_GEAR", falas)
        b = Avisos()
        voar(b, 0.0, 1.0, lambda t: cruzeiro(radar=100.0))
        falas, _ = voar(b, 1.0, 4.0, lambda t: cruzeiro(radar=100.0, velocidade=180.0))
        self.assertIn("TOO_LOW_TERRAIN", falas)
        c = Avisos()
        voar(c, 0.0, 1.0, lambda t: cruzeiro(radar=100.0, trem=None))
        falas, _ = voar(c, 1.0, 4.0, lambda t: cruzeiro(radar=100.0, velocidade=70.0, trem=None))
        self.assertEqual(falas, [])

    def test_bank_angle_uma_vez_por_inclinacao(self):
        a = Avisos()
        voar(a, 0.0, 1.0, lambda t: cruzeiro(radar=200.0))
        falas, _ = voar(a, 1.0, 10.0, lambda t: cruzeiro(radar=200.0, rolagem=60.0))
        self.assertEqual(falas, ["BANK_ANGLE"])
        voar(a, 11.0, 1.0, lambda t: cruzeiro(radar=200.0))
        falas, _ = voar(a, 12.0, 2.0, lambda t: cruzeiro(radar=200.0, rolagem=-60.0))
        self.assertEqual(falas, ["BANK_ANGLE"])
        falas, _ = voar(a, 14.0, 5.0, lambda t: cruzeiro(radar=2000.0, rolagem=90.0))
        self.assertEqual(falas, [])

    def test_overspeed_repete(self):
        a = Avisos()
        falas, niveis = voar(a, 0.0, 7.0, lambda t: cruzeiro(radar=3000.0, pressao=60_000.0))
        self.assertGreaterEqual(falas.count("OVERSPEED"), 2)
        self.assertEqual(niveis, {1})

    def test_pull_up_ganha_de_tudo(self):
        a = Avisos()
        voar(a, 0.0, 1.0, lambda t: cruzeiro(radar=100.0, velocidade=70.0))
        falas, _ = voar(a, 1.0, 3.0, lambda t: cruzeiro(radar=100.0, vv=-40.0, velocidade=70.0, rolagem=60.0,
                                                          pressao=60_000.0))
        self.assertEqual(falas[0], "PULL_UP")

    def test_nao_fala_duas_frases_juntas(self):
        a = Avisos()
        vezes = []
        t = 0.0
        while t < 10.0:
            fala = a.atualizar(cruzeiro(radar=100.0, velocidade=70.0, rolagem=60.0, pressao=60_000.0), t)
            if fala is not None:
                vezes.append(t)
            t += PASSO
        self.assertTrue(all(b - a_ >= avisos.INTERVALO_ENTRE_FALAS - 1e-9 for a_, b in zip(vezes, vezes[1:])))

    def test_toda_fala_tem_frase(self):
        for nome, _, _ in avisos.AVISOS:
            self.assertIn(nome, FRASES)
        for pes in avisos.CHAMADAS:
            self.assertIn(pes, FRASES)
        self.assertAlmostEqual(PES * 100, 30.48)


class TestNaPonte(unittest.TestCase):
    def test_telemetria_vira_voo(self):
        t = Telemetria(
            pitch=0.0, rumo=90.0, rolagem=12.0, velocidades={"SUP": (-3.0, 0.0, 4.0)},
            altitude=500.0, radar=80.0, raio_planeta=600_000.0, posicao=(600_500.0, 0.0, 0.0),
            apoastro=None, periastro=None, tempo_apoastro=None, tempo_periastro=None,
            acelerador=0.5, alvo=None, posicao_alvo=None, manobra=None, sistemas={"SAS": False, "RCS": False},
            no_ar=True, trem=True, pressao=4000.0,
        )
        v = voo_dos_avisos(t)
        self.assertEqual((v.radar, v.vv, v.velocidade, v.rolagem, v.trem, v.no_ar), (80.0, -3.0, 5.0, 12.0, True, True))
        self.assertEqual(v.pressao, 4000.0)


if __name__ == "__main__":
    unittest.main()
