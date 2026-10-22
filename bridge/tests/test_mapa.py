"""Testes do mapa da órbita (mapa.py e o botão MAPA em sistemas.py), sem o KSP.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_mapa.py
    python bridge/tests/test_mapa.py -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mapa import LUAS_MAX, MapaDemo, Orbita, anomalia_de, linha_valida, linhas_do_mapa, media_de, nome_curto
from sistemas import Sistemas


def dados_de_exemplo():
    corpo = {"nome": "Kerbin", "raio": 600_000, "topo": 70_000, "soi": 84_159_286.5, "mu": 3.5316e12, "giro": 361.27}
    return {
        "corpo": corpo,
        "nave": Orbita(690_000.4, 0.0144928, 5.04, 30.0, 359.99, 123.45),
        "luas": [("Mun", 200_000, Orbita(12_000_000, 0.0, 0.0, 0.0, 0.0, 10.0))],
        "alvo": None,
        "no": None,
    }


class LinhasDoMapa(unittest.TestCase):
    def test_todas_validas_e_curtas(self):
        for linha in linhas_do_mapa(dados_de_exemplo()):
            self.assertTrue(linha.isascii(), linha)
            self.assertLessEqual(len(linha), 31, linha)
            self.assertTrue(linha_valida(linha), linha)

    def test_valores(self):
        linhas = linhas_do_mapa(dados_de_exemplo())
        for esperada in ("MAP CORPO KERBIN", "MAP RAIO 600000", "MAP SOI 84159286", "MAP MU 3532", "MAP GIRO 13",
                         "MAP NAVE A 690000", "MAP NAVE E 14493", "MAP NAVE INC 50", "MAP NAVE LAN 300",
                         "MAP NAVE ARG 0", "MAP NAVE ANOM 1234", "MAP L1 NOME MUN", "MAP L1 RAIO 200000",
                         "MAP L1 A 12000000"):
            self.assertIn(esperada, linhas)

    def test_ausentes_viram_off(self):
        linhas = linhas_do_mapa(dados_de_exemplo())
        self.assertIn("MAP ALVO OFF", linhas)
        self.assertIn("MAP NO OFF", linhas)
        for i in range(2, LUAS_MAX + 1):
            self.assertIn(f"MAP L{i} OFF", linhas)

    def test_sol_sem_esfera_de_influencia(self):
        dados = dados_de_exemplo()
        dados["corpo"]["soi"] = math.inf
        self.assertIn("MAP SOI OFF", linhas_do_mapa(dados))

    def test_hiperbole_tem_semieixo_negativo(self):
        dados = dados_de_exemplo()
        dados["nave"] = Orbita(-2_500_000, 1.35, 0.0, 0.0, 0.0, 20.0)
        linhas = linhas_do_mapa(dados)
        self.assertIn("MAP NAVE A -2500000", linhas)
        self.assertIn("MAP NAVE E 1350000", linhas)
        self.assertTrue(all(linha_valida(linha) for linha in linhas))

    def test_alvo_e_no(self):
        dados = dados_de_exemplo()
        dados["alvo"] = {"nome": "Estação um", "orbita": Orbita(760_000, 0.01, 0.2, 10, 200, 5),
                         "dmin": 3_456.7, "tmin": None, "nmin": 140.0, "amin": None}
        dados["no"] = {"orbita": Orbita(840_000, 0.19, 5, 30, 60, 0), "nanom": 359.96, "t": 1_234.4, "dv": 123.44}
        linhas = linhas_do_mapa(dados)
        for esperada in ("MAP ALVO NOME ESTACAO_UM", "MAP ALVO DMIN 3457", "MAP ALVO TMIN OFF", "MAP ALVO NMIN 1400",
                         "MAP ALVO AMIN OFF", "MAP NO A 840000", "MAP NO NANOM 0", "MAP NO T 1234", "MAP NO DV 1234"):
            self.assertIn(esperada, linhas)
        self.assertTrue(all(linha_valida(linha) for linha in linhas))

    def test_conferidor_recusa(self):
        for linha in ("MAP NAVE X 10", "MAP L5 A 10", "MAP CORPO kerbin", "MAP NAVE A 1.5", "MAP NO NOME X",
                      "MAP RAIO OFF", "MAP L1 NOME " + "A" * 17, "MAPA 1", "MAP NAVE A 1 2"):
            self.assertFalse(linha_valida(linha), linha)


class Nomes(unittest.TestCase):
    def test_tira_acento_e_espaco(self):
        self.assertEqual(nome_curto("Estação um"), "ESTACAO_UM")

    def test_corta_em_16(self):
        self.assertEqual(nome_curto("AEAS - SmalLifter Debris"), "AEAS___SMALLIFTE")


class Kepler(unittest.TestCase):
    def test_ida_e_volta_na_elipse(self):
        for e in (0.0, 0.3, 0.95):
            for graus in (0, 10, 179, 181, 300):
                media = media_de(e, math.radians(graus))
                volta = math.degrees(anomalia_de(e, media)) % 360
                self.assertAlmostEqual(volta, graus % 360, places=6)

    def test_ida_e_volta_na_hiperbole(self):
        for graus in (-100, -30, 0, 45, 110):
            media = media_de(1.5, math.radians(graus))
            self.assertAlmostEqual(math.degrees(anomalia_de(1.5, media)), graus, places=6)


class Demo(unittest.TestCase):
    def test_linhas_da_demo_sao_validas(self):
        demo = MapaDemo(inicio=0.0)
        for agora in (0.0, 30.0, 75.0, 200.0):
            linhas = linhas_do_mapa(demo.dados(agora))
            self.assertTrue(all(linha_valida(linha) for linha in linhas))
        self.assertIn("MAP NO OFF", linhas_do_mapa(demo.dados(30.0)))
        self.assertNotIn("MAP NO OFF", linhas_do_mapa(demo.dados(75.0)))

    def test_a_nave_anda(self):
        demo = MapaDemo(inicio=0.0)
        self.assertNotEqual(demo.dados(0.0)["nave"].anom, demo.dados(60.0)["nave"].anom)


class BotaoMapa(unittest.TestCase):
    def test_liga_e_desliga(self):
        s = Sistemas(None)
        self.assertTrue(s.tratar("BTN MAPA 1", 0.0, 90.0, 1000.0))
        self.assertTrue(s.mapa)
        self.assertEqual(s.pagina, "MAPA")
        s.tratar("BTN MAPA 0", 0.1, 90.0, 1000.0)
        self.assertTrue(s.mapa)
        s.tratar("BTN MAPA 1", 1.0, 90.0, 1000.0)
        self.assertFalse(s.mapa)
        s.atualizar(1.0)
        self.assertEqual(s.pagina, "NAV")

    def test_mapa_vira_a_pagina_base(self):
        s = Sistemas(None)
        s.tratar("BTN MAPA 1", 0.0, 90.0, 1000.0)
        s.pagina_base = "MAPA"
        s.abrir("SAS", 1.0)
        s.atualizar(20.0)
        self.assertEqual(s.pagina, "MAPA")

    def test_luz_vai_so_para_o_painel(self):
        s = Sistemas(None)
        s.tratar("BTN MAPA 1", 0.0, 90.0, 1000.0)
        luzes = s.luzes(False, False, None, None, False, False, {})
        self.assertEqual(luzes["MAPA"], "MAPA 1")
        self.assertNotIn("MAPA", s.tela(luzes, None, False))


if __name__ == "__main__":
    unittest.main()
