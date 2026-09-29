"""Testes do painel de sistemas de controle (sistemas.py e a parte dele em mfd.py), sem o KSP.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_sistemas.py
    python bridge/tests/test_sistemas.py -v
"""

import math
import os
import sys
import time
import unittest

# A ponte fica na pasta de cima (bridge/).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import sistemas
from mfd import FBW_FECHADO, Scripts, Telemetria, angulo_ate, erro_do_sas

# O fly by wire fica em scripts/, ao lado de bridge/.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import fbw  # noqa: E402
from sistemas import CorDoModo, MenuPiloto, Remetente, Sistemas


class Acoes:
    """Guarda o que o painel pediu."""

    def __init__(self):
        self.pedidos = []

    def alternar(self, nome):
        self.pedidos.append(("alternar", nome))

    def escolher_modo(self, nome):
        self.pedidos.append(("modo", nome))

    def comando_fbw(self, linha):
        self.pedidos.append(("fbw", linha))


def novo():
    acoes = Acoes()
    return Sistemas(acoes), acoes


class TestMenu(unittest.TestCase):
    def test_comeca_onde_o_aviao_esta(self):
        menu = MenuPiloto()
        menu.iniciar(92.6, 1234.0)
        self.assertEqual(menu.valores, {"HDG": 93, "ALT": 1230, "VS": 0})
        menu.iniciar(10.0, 10.0)   # só na primeira vez
        self.assertEqual(menu.valores["HDG"], 93)

    def test_girar_move_o_cursor_sem_passar_das_pontas(self):
        menu = MenuPiloto()
        menu.iniciar(0, 0)
        menu.girar(1, 0.0)
        self.assertEqual(menu.linha, "ALT")
        menu.girar(1, 1.0)
        menu.girar(1, 2.0)
        self.assertEqual(menu.linha, "VS")
        menu.girar(-1, 3.0)
        menu.girar(-1, 4.0)
        menu.girar(-1, 5.0)
        self.assertEqual(menu.linha, "HDG")

    def test_apertar_escolhe_e_girar_muda_o_valor(self):
        menu = MenuPiloto()
        menu.iniciar(358, 1000)
        menu.apertar(0.0)
        menu.soltar()
        self.assertTrue(menu.editando)
        menu.girar(1, 1.0)
        menu.girar(1, 2.0)
        menu.girar(1, 3.0)
        self.assertEqual(menu.valores["HDG"], 1)        # dá a volta
        menu.girar(-2, 4.0)                              # rápido: dois cliques de uma vez
        self.assertEqual(menu.valores["HDG"], 341)
        menu.apertar(5.0)
        menu.soltar()
        self.assertFalse(menu.editando)

    def test_girar_rapido_anda_dez_vezes_mais(self):
        menu = MenuPiloto()
        menu.iniciar(0, 1000)
        menu.cursor = 1
        menu.editando = True
        menu.girar(1, 10.0)
        self.assertEqual(menu.valores["ALT"], 1010)
        menu.girar(1, 10.05)                             # 50 ms depois do anterior
        self.assertEqual(menu.valores["ALT"], 1110)

    def test_limites(self):
        menu = MenuPiloto()
        menu.iniciar(0, 0)
        menu.cursor, menu.editando = 1, True
        menu.girar(-5, 0.0)
        self.assertEqual(menu.valores["ALT"], 0)
        menu.cursor = 2
        for i in range(20):
            menu.girar(10, i)
        self.assertEqual(menu.valores["VS"], sistemas.LIMITES["VS"][1])

    def test_segurar_liga_o_modo_uma_vez_e_nao_escolhe_a_linha(self):
        menu = MenuPiloto()
        menu.iniciar(0, 0)
        menu.apertar(0.0)
        self.assertIsNone(menu.segurou(0.5))
        self.assertEqual(menu.segurou(1.0), "HDG")
        self.assertIsNone(menu.segurou(2.0))
        menu.soltar()
        self.assertFalse(menu.editando)


class TestCor(unittest.TestCase):
    def test_azul_virando_e_verde_no_marcador_com_folga(self):
        cor = CorDoModo()
        self.assertEqual(cor.atualizar("PRO", 30.0), "A")
        self.assertEqual(cor.atualizar("PRO", 1.5), "V")
        self.assertEqual(cor.atualizar("PRO", 3.5), "V")   # dentro da folga
        self.assertEqual(cor.atualizar("PRO", 5.0), "A")
        self.assertEqual(cor.atualizar("PRO", None), "A")  # sem marcador

    def test_modo_novo_comeca_azul_e_estab_e_verde(self):
        cor = CorDoModo()
        cor.atualizar("PRO", 0.5)
        self.assertEqual(cor.atualizar("NRM", 0.5), "V")
        self.assertEqual(cor.atualizar("ESTAB", None), "V")


class TestSistemas(unittest.TestCase):
    def test_korry_de_modo_escolhe_e_abre_a_roda_do_sas(self):
        s, acoes = novo()
        self.assertTrue(s.tratar("BTN SAS_PRO 1", 0.0, 0, 0))
        self.assertTrue(s.tratar("BTN SAS_PRO 0", 0.1, 0, 0))
        self.assertEqual(acoes.pedidos, [("modo", "PRO")])
        self.assertEqual(s.pagina, "SAS")
        s.atualizar(sistemas.PAGINA_DURA + 0.1)
        self.assertEqual(s.pagina, "NAV")

    def test_sas_rcs_fbw_e_trava(self):
        s, acoes = novo()
        for nome in ("SAS", "RCS", "FBW", "TRAVA"):
            s.tratar(f"BTN {nome} 1", 0.0, 0, 0)
        self.assertEqual(
            acoes.pedidos,
            [("alternar", "SAS"), ("alternar", "RCS"), ("fbw", "CMD FBW"), ("fbw", "CMD TRAVA")],
        )

    def test_encoder_abre_a_pagina_antes_de_mexer(self):
        s, acoes = novo()
        s.tratar("ENC AP 1", 0.0, 90, 1000)
        self.assertEqual(s.pagina, "AP")
        self.assertEqual(s.menu.linha, "HDG")    # o primeiro clique só abriu a página
        s.tratar("ENC AP 1", 1.0, 90, 1000)
        self.assertEqual(s.menu.linha, "ALT")

    def test_segurar_o_encoder_manda_o_modo_ao_fbw(self):
        s, acoes = novo()
        s.tratar("BTN AP 1", 0.0, 90, 1000)       # abre a página
        s.tratar("BTN AP 0", 0.1, 90, 1000)
        s.tratar("ENC AP 1", 0.5, 90, 1000)       # cursor no ALT
        s.tratar("BTN AP 1", 1.0, 90, 1000)
        s.atualizar(1.5)
        s.atualizar(2.1)
        s.tratar("BTN AP 0", 2.5, 90, 1000)
        self.assertIn(("fbw", "CMD ALT"), acoes.pedidos)
        self.assertFalse(s.menu.editando)

    def test_valores_vao_ao_fbw_quando_mudam_e_de_tempos_em_tempos(self):
        s, acoes = novo()
        s.tratar("ENC AP 1", 0.0, 90, 1000)
        s.atualizar(0.0)
        self.assertIn(("fbw", "APV HDG 90"), acoes.pedidos)
        acoes.pedidos.clear()
        s.atualizar(0.5)
        self.assertEqual(acoes.pedidos, [])
        s.atualizar(1.1)
        self.assertEqual(len(acoes.pedidos), 3)

    def test_luzes(self):
        s, _ = novo()
        fbw = {"LEI": "LEI FBW", "TRAVA": "TRAVA OFF", "APL HDG": "APL HDG 1"}
        luzes = s.luzes(True, False, "PRO", 20.0, True, True, fbw)
        self.assertEqual(luzes["SASM"], "SASM PRO A")
        self.assertEqual(luzes["SEMEC"], "SEMEC 1")
        self.assertEqual(luzes["SEMMP"], "SEMMP 0")        # RCS desligado: não avisa
        self.assertEqual(s.luzes(True, False, "PRO", 1.0, False, False, fbw)["SASM"], "SASM PRO V")
        self.assertEqual(s.luzes(False, False, "PRO", 1.0, False, False, fbw)["SASM"], "SASM OFF")
        luzes_estol = s.luzes(True, False, "PRO", 1.0, False, False, {"ESTOL": "ESTOL 1"})
        self.assertEqual(luzes_estol["ESTOL"], "ESTOL 1")                     # a luz do painel
        self.assertEqual(s.tela(luzes_estol, 1.0, True)["ESTOL"], "ESTOL 1")  # e o alarme da tela
        tela = s.tela(luzes, 20.04, True)
        self.assertEqual(tela["SASE"], "SASE 200")
        self.assertEqual(tela["PAG"], "PAG NAV")
        self.assertNotIn("SAS", tela)                      # vai pelo Transmissor
        for linha in list(luzes.values()) + list(tela.values()):
            self.assertLessEqual(len(linha), 31)

    def test_linha_de_outro_painel(self):
        s, _ = novo()
        self.assertFalse(s.tratar("BTN STAGE 1", 0.0, 0, 0))
        self.assertFalse(s.tratar("ENC AP x", 0.0, 0, 0))


class TestRemetente(unittest.TestCase):
    def test_manda_quando_muda_e_a_cada_segundo(self):
        enviadas = []
        r = Remetente(enviadas.append)
        r.mandar({"A": "A 1", "B": "B 1"}, 0.0)
        r.mandar({"A": "A 1", "B": "B 2"}, 0.5)
        self.assertEqual(enviadas, ["A 1", "B 1", "B 2"])
        r.mandar({"A": "A 1", "B": "B 2"}, 1.1)
        self.assertEqual(enviadas[3:], ["A 1", "B 2"])


def telemetria(**kwargs):
    base = dict(
        pitch=0.0, rumo=90.0, rolagem=0.0,
        velocidades={"SUP": (0.0, 0.0, 200.0), "ORB": (0.0, 0.0, 2200.0)},
        altitude=80_000.0, radar=80_000.0, raio_planeta=600_000.0,
        posicao=(680_000.0, 0.0, 0.0), apoastro=None, periastro=None,
        tempo_apoastro=None, tempo_periastro=None, acelerador=0.0,
        alvo=None, posicao_alvo=None, manobra=None, sistemas={"SAS": True, "RCS": False},
    )
    base.update(kwargs)
    return Telemetria(**base)


class TestErro(unittest.TestCase):
    def test_angulo_ate(self):
        self.assertAlmostEqual(angulo_ate(0.0, 90.0, (0.0, 0.0, 5.0)), 0.0)
        self.assertAlmostEqual(angulo_ate(0.0, 90.0, (1.0, 0.0, 0.0)), 90.0)
        self.assertIsNone(angulo_ate(0.0, 0.0, (0.0, 0.0, 0.0)))

    def test_erro_de_cada_modo_com_o_nariz_para_leste(self):
        # Órbita para leste no equador: normal para o norte, radial para cima.
        casos = {"PRO": 0.0, "RETRO": 180.0, "NRM": 90.0, "ANRM": 90.0, "RFORA": 90.0, "RDENTRO": 90.0}
        for modo, esperado in casos.items():
            with self.subTest(modo=modo):
                self.assertAlmostEqual(erro_do_sas(telemetria(sas_modo=modo), "ORB"), esperado, delta=0.01)
        # Nariz para o norte: agora o normal está na frente.
        self.assertAlmostEqual(erro_do_sas(telemetria(sas_modo="NRM", rumo=0.0), "ORB"), 0.0, delta=0.01)
        self.assertAlmostEqual(erro_do_sas(telemetria(sas_modo="RFORA", pitch=90.0), "ORB"), 0.0, delta=0.01)

    def test_alvo_manobra_e_estab(self):
        t = telemetria(sas_modo="ALVO", alvo="X", posicao_alvo=(0.0, 100.0, 100.0))
        self.assertAlmostEqual(erro_do_sas(t, "ALVO"), 45.0, delta=0.01)
        self.assertIsNone(erro_do_sas(telemetria(sas_modo="ALVO"), "ORB"))
        self.assertIsNone(erro_do_sas(telemetria(sas_modo="MAN"), "ORB"))
        self.assertIsNone(erro_do_sas(telemetria(sas_modo="ESTAB"), "ORB"))
        self.assertTrue(math.isclose(erro_do_sas(telemetria(sas_modo="MAN", manobra=(0, 0, -3)), "ORB"), 180.0))


class TestConversaComOFbw(unittest.TestCase):
    """O fbw.py e a ponte da tela, de verdade, por UDP neste computador."""

    def setUp(self):
        self.ponte = Scripts(porta=0)
        porta = self.ponte._socket.getsockname()[1]
        self.tela = fbw.TelaFbw("127.0.0.1")
        self.tela._destino = ("127.0.0.1", porta)

    def tearDown(self):
        self.ponte.fechar()
        self.tela._socket.close()

    def esperar(self, condicao):
        fim = time.monotonic() + 2.0
        while time.monotonic() < fim:
            if condicao():
                return True
            time.sleep(0.01)
        return False

    def test_estado_vai_e_comando_volta(self):
        guiagem = fbw.FlyByWire()
        guiagem.lei = fbw.FBW
        guiagem.comando = (2.0, 90.0)
        guiagem.altitude_travada = 1830.0
        self.assertEqual(self.ponte.estado_fbw()["LEI"], "LEI OFF")   # antes de o fbw.py mandar
        self.tela.enviar(guiagem)
        self.assertTrue(self.esperar(lambda: self.ponte.estado_fbw()["LEI"] == "LEI FBW"))
        self.assertEqual(self.ponte.estado_fbw()["TRAVA"], "TRAVA 1830")
        self.assertEqual(self.ponte.estado_fbw()["ESTOL"], "ESTOL 0")
        guiagem.estol = True
        self.tela.enviar(guiagem)
        self.assertTrue(self.esperar(lambda: self.ponte.estado_fbw()["ESTOL"] == "ESTOL 1"))
        guiagem.estol = False
        self.assertEqual(self.ponte.ponto_fbw(), (2.0, 90.0))

        self.ponte.comando_fbw("CMD HDG")
        self.ponte.comando_fbw("APV HDG 45")
        linhas = []
        self.assertTrue(self.esperar(lambda: linhas.extend(self.tela.receber()) or len(linhas) >= 2))
        for linha in linhas:
            fbw.executar(linha, guiagem)
        self.assertTrue(guiagem.ap["HDG"])
        self.assertEqual(guiagem.ap_valores["HDG"], 45.0)

    def test_sem_o_fbw_tudo_desligado(self):
        self.assertEqual(self.ponte.estado_fbw(), FBW_FECHADO)
        self.ponte.comando_fbw("CMD FBW")   # sem endereço: não faz nada


if __name__ == "__main__":
    unittest.main()
