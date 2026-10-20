"""Testes do painel de scripts (painel_scripts.py e a parte dele em mfd.py), sem o KSP.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_scripts.py
    python bridge/tests/test_scripts.py -v
"""

import json
import os
import socket
import sys
import tempfile
import time
import unittest
from unittest import mock

# A ponte fica na pasta de cima (bridge/).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import mfd
import painel_scripts
import sistemas
from mfd import CAMPOS_SUBIDA, Scripts, Transmissor
from painel_scripts import MOSTRA_FIM, SEGURAR, MenuSubida, PainelScripts, Processo
from sistemas import RAPIDO, Sistemas

# O pouso e a subida ficam em scripts/, ao lado de bridge/.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import pouso  # noqa: E402
import subida  # noqa: E402


class ProcessoFalso:
    """Faz o papel de um script: roda até terminar() ou abortar()."""

    def __init__(self):
        self.vivo = False
        self.codigo = None
        self.iniciado = self.abortado = 0

    def iniciar(self):
        self.vivo, self.codigo = True, None
        self.iniciado += 1

    def abortar(self):
        self.abortado += 1
        self.terminar(pouso.INTERROMPIDO)

    def terminar(self, codigo):
        self.vivo, self.codigo = False, codigo

    def rodando(self):
        return self.vivo

    def fechar(self):
        pass


class TestPainelScripts(unittest.TestCase):
    def setUp(self):
        self.processo = ProcessoFalso()
        self.painel = PainelScripts({"POUSO": self.processo})

    def segurar(self, desde, ate):
        self.painel.tratar("BTN POUSO 1", desde)
        for i in range(round((ate - desde) * 10) + 1):
            self.painel.atualizar(desde + i / 10)

    def test_soltar_antes_nao_abre(self):
        self.painel.tratar("BTN POUSO 1", 0.0)
        self.painel.atualizar(1.0)
        self.assertEqual(self.painel.estado("POUSO", 1.0), "LIGA 4")
        self.painel.atualizar(SEGURAR - 0.1)
        self.assertEqual(self.painel.estado("POUSO", SEGURAR - 0.1), "LIGA 1")
        self.painel.tratar("BTN POUSO 0", SEGURAR - 0.1)
        self.painel.atualizar(SEGURAR + 1)
        self.assertEqual(self.processo.iniciado, 0)
        self.assertEqual(self.painel.estado("POUSO", SEGURAR + 1), "OFF")
        self.assertIsNone(self.painel.em_uso(SEGURAR + 1))

    def test_segurar_abre_uma_vez_so(self):
        self.segurar(0.0, SEGURAR + 3)   # continua apertado depois dos 5 s
        self.assertEqual(self.processo.iniciado, 1)
        # O aperto já foi usado: continuar segurando não conta para abortar.
        self.assertEqual(self.painel.estado("POUSO", SEGURAR + 3), "ATIVO")
        self.painel.tratar("BTN POUSO 0", SEGURAR + 3)
        self.assertEqual(self.painel.estado("POUSO", SEGURAR + 3), "ATIVO")
        self.assertEqual(self.painel.luzes(SEGURAR + 3), {"SCR POUSO": "SCR POUSO ATIVO"})
        self.assertEqual(self.painel.em_uso(SEGURAR + 3), "POUSO")
        self.assertEqual(self.processo.abortado, 0)

    def test_segurar_de_novo_aborta(self):
        self.segurar(0.0, SEGURAR)
        self.painel.tratar("BTN POUSO 0", SEGURAR)
        self.painel.tratar("BTN POUSO 1", 10.0)
        self.assertEqual(self.painel.estado("POUSO", 10.0), "DESL 5")
        self.painel.atualizar(10.0 + SEGURAR)
        self.assertEqual(self.processo.abortado, 1)
        self.painel.tratar("BTN POUSO 0", 10.0 + SEGURAR)
        self.painel.atualizar(10.0 + SEGURAR)
        self.assertEqual(self.painel.estado("POUSO", 16.0), "ABORT")
        self.assertEqual(self.painel.estado("POUSO", 15.0 + MOSTRA_FIM + 0.1), "OFF")

    def test_pousou_e_falhou(self):
        self.segurar(0.0, SEGURAR)
        self.painel.tratar("BTN POUSO 0", SEGURAR)
        self.processo.terminar(pouso.POUSOU)
        self.painel.atualizar(20.0)
        self.assertEqual(self.painel.estado("POUSO", 20.0), "FIM")
        self.assertEqual(self.painel.em_uso(20.0), "POUSO")   # a tela mostra o fim
        self.assertIsNone(self.painel.em_uso(20.0 + MOSTRA_FIM))

        self.segurar(40.0, 40.0 + SEGURAR)   # de novo, e desta vez falha
        self.painel.tratar("BTN POUSO 0", 46.0)
        self.processo.terminar(pouso.NAO_POUSOU)
        self.painel.atualizar(50.0)
        self.assertEqual(self.painel.estado("POUSO", 50.0), "FALHA")

    def test_um_script_por_vez(self):
        outro = ProcessoFalso()
        painel = PainelScripts({"POUSO": self.processo, "EXEC": outro})
        painel.tratar("BTN POUSO 1", 0.0)
        painel.atualizar(SEGURAR)
        painel.tratar("BTN EXEC 1", 1.0)
        painel.atualizar(1.0 + SEGURAR)
        self.assertEqual(outro.iniciado, 0)
        self.assertEqual(painel.ativo(), "POUSO")

    def test_linhas_de_outros_paineis(self):
        self.assertFalse(self.painel.tratar("BTN SAS 1", 0.0))
        self.assertFalse(self.painel.tratar("BTN POUSO", 0.0))
        self.assertFalse(self.painel.tratar("ENC POUSO 1", 0.0))

    def test_pagina_do_script_na_tela(self):
        s = Sistemas(None)
        s.abrir("POUSO", 0.0)
        s.pagina_base = "POUSO"          # o script está voando
        s.abrir("SAS", 1.0)              # um toque no painel de sistemas no meio do pouso
        s.atualizar(1.0 + sistemas.PAGINA_DURA)
        self.assertEqual(s.pagina, "POUSO")   # volta para o pouso, e não para a navball
        s.pagina_base = "NAV"
        s.atualizar(2.0 + sistemas.PAGINA_DURA)
        self.assertEqual(s.pagina, "NAV")


class TestMenuSubida(unittest.TestCase):
    def setUp(self):
        self.menu = MenuSubida()

    def escolher(self, linha):
        self.menu.cursor = ("ALT", "INC", "PLANO").index(linha)
        self.menu.apertar(0.0)
        self.menu.soltar()
        self.assertTrue(self.menu.editando)

    def test_valores_iniciais(self):
        self.assertEqual(self.menu.valores, {"ALT": 80, "INC": 0, "PLANO": 0})
        self.assertEqual(self.menu.cursor, 0)
        self.assertFalse(self.menu.editando)
        self.assertEqual(self.menu.linha, "ALT")

    def test_cursor_anda_e_para_nas_pontas(self):
        self.menu.girar(1, 10.0)
        self.assertEqual(self.menu.linha, "INC")
        self.menu.girar(1, 20.0)
        self.assertEqual(self.menu.linha, "PLANO")
        self.menu.girar(1, 30.0)
        self.assertEqual(self.menu.linha, "PLANO")
        self.menu.girar(-5, 40.0)
        self.assertEqual(self.menu.linha, "ALT")
        self.assertEqual(self.menu.valores, {"ALT": 80, "INC": 0, "PLANO": 0})

    def test_apertar_e_soltar_escolhe_e_sai(self):
        self.menu.apertar(0.0)
        self.assertFalse(self.menu.editando)
        self.menu.soltar()
        self.assertTrue(self.menu.editando)
        self.menu.apertar(5.0)
        self.menu.soltar()
        self.assertFalse(self.menu.editando)

    def test_soltar_sem_apertar_nao_faz_nada(self):
        self.menu.soltar()
        self.assertFalse(self.menu.editando)

    def test_altitude_devagar_e_rapido(self):
        self.escolher("ALT")
        self.menu.girar(1, 10.0)
        self.assertEqual(self.menu.valores["ALT"], 81)
        self.menu.girar(-1, 11.0)
        self.assertEqual(self.menu.valores["ALT"], 80)
        self.menu.girar(1, 11.0 + RAPIDO / 2)
        self.assertEqual(self.menu.valores["ALT"], 90)
        self.menu.girar(2, 20.0)
        self.assertEqual(self.menu.valores["ALT"], 110)
        self.menu.girar(-1, 30.0)
        self.assertEqual(self.menu.valores["ALT"], 109)

    def test_inclinacao_devagar_e_rapido(self):
        self.escolher("INC")
        self.menu.girar(1, 10.0)
        self.assertEqual(self.menu.valores["INC"], 1)
        self.menu.girar(3, 20.0)
        self.assertEqual(self.menu.valores["INC"], 31)

    def test_limites(self):
        self.escolher("ALT")
        self.menu.girar(-1000, 10.0)
        self.assertEqual(self.menu.valores["ALT"], 10)
        self.menu.girar(-1, 20.0)
        self.assertEqual(self.menu.valores["ALT"], 10)
        self.menu.girar(1000, 30.0)
        self.assertEqual(self.menu.valores["ALT"], 5000)
        self.menu.sair()
        self.escolher("INC")
        self.menu.girar(-1, 40.0)
        self.assertEqual(self.menu.valores["INC"], 0)
        self.menu.girar(1000, 50.0)
        self.assertEqual(self.menu.valores["INC"], 180)

    def test_plano_troca_a_cada_linha_de_giro(self):
        self.escolher("PLANO")
        self.menu.girar(1, 10.0)
        self.assertEqual(self.menu.valores["PLANO"], 1)
        self.menu.girar(1, 20.0)
        self.assertEqual(self.menu.valores["PLANO"], 0)
        self.menu.girar(-3, 30.0)
        self.assertEqual(self.menu.valores["PLANO"], 1)
        self.menu.girar(-1, 30.01)
        self.assertEqual(self.menu.valores["PLANO"], 0)

    def test_sair(self):
        self.escolher("INC")
        self.menu.apertar(1.0)
        self.menu.sair()
        self.menu.soltar()
        self.assertFalse(self.menu.editando)
        self.assertEqual(self.menu.linha, "INC")

    def test_linhas(self):
        self.assertEqual(
            self.menu.linhas(),
            {"SBV ALT": "SBV ALT 80", "SBV INC": "SBV INC 0", "SBV PLANO": "SBV PLANO 0", "SBC": "SBC ALT 0"},
        )
        self.escolher("PLANO")
        self.menu.girar(1, 10.0)
        self.assertEqual(self.menu.linhas()["SBV PLANO"], "SBV PLANO 1")
        self.assertEqual(self.menu.linhas()["SBC"], "SBC PLANO 1")
        for linha in self.menu.linhas().values():
            self.assertLessEqual(len(linha), 31)
            self.assertTrue(linha.isascii())

    def test_argumentos(self):
        self.assertEqual(self.menu.argumentos(), ["--altitude", "80000", "--inclinacao", "0"])
        self.menu.valores.update({"ALT": 250, "INC": 98, "PLANO": 1})
        self.assertEqual(self.menu.argumentos(), ["--altitude", "250000", "--inclinacao", "98", "--plano-do-alvo"])


class TestPainelComMenu(unittest.TestCase):
    def setUp(self):
        self.pouso = ProcessoFalso()
        self.lancar = ProcessoFalso()
        self.menu = MenuSubida()
        self.painel = PainelScripts({"POUSO": self.pouso, "LANCAR": self.lancar}, self.menu)

    def test_encoder_com_a_tela_noutra_pagina_so_pede_a_subida(self):
        for pagina in ("NAV", "SAS", "AP", "POUSO"):
            self.assertEqual(self.painel.tratar("ENC SUB 1", 0.0, pagina), "SUBIDA")
            self.assertEqual(self.painel.tratar("BTN SUB 1", 0.1, pagina), "SUBIDA")
            self.assertEqual(self.painel.tratar("BTN SUB 0", 0.2, pagina), "SUBIDA")
        self.assertEqual(self.painel.tratar("ENC SUB 1", 0.0), "SUBIDA")
        self.assertEqual(self.menu.cursor, 0)
        self.assertFalse(self.menu.editando)
        self.assertEqual(self.menu.valores, {"ALT": 80, "INC": 0, "PLANO": 0})

    def test_aperto_que_abriu_a_pagina_nao_escolhe_a_linha(self):
        self.assertEqual(self.painel.tratar("BTN SUB 1", 0.0, "NAV"), "SUBIDA")
        self.assertEqual(self.painel.tratar("BTN SUB 0", 0.1, "SUBIDA"), "SUBIDA")
        self.assertFalse(self.menu.editando)

    def test_encoder_com_a_tela_na_subida_mexe_no_menu(self):
        self.assertEqual(self.painel.tratar("ENC SUB 1", 0.0, "SUBIDA"), "SUBIDA")
        self.assertEqual(self.menu.linha, "INC")
        self.assertEqual(self.painel.tratar("BTN SUB 1", 1.0, "SUBIDA"), "SUBIDA")
        self.assertEqual(self.painel.tratar("BTN SUB 0", 1.1, "SUBIDA"), "SUBIDA")
        self.assertTrue(self.menu.editando)
        self.assertEqual(self.painel.tratar("ENC SUB 1", 2.0, "SUBIDA"), "SUBIDA")
        self.assertEqual(self.menu.valores["INC"], 1)
        self.painel.tratar("BTN SUB 1", 3.0, "SUBIDA")
        self.painel.tratar("BTN SUB 0", 3.1, "SUBIDA")
        self.assertFalse(self.menu.editando)

    def test_korry_pede_a_pagina_do_script(self):
        self.assertEqual(self.painel.tratar("BTN LANCAR 1", 0.0), "SUBIDA")
        self.assertEqual(self.painel.tratar("BTN LANCAR 0", 0.1), "")
        self.assertEqual(self.painel.tratar("BTN POUSO 1", 1.0), "POUSO")
        self.assertEqual(self.painel.tratar("BTN POUSO 0", 1.1), "")
        self.assertEqual(self.painel.estado("POUSO", 2.0), "OFF")

    def test_linhas_de_outros_paineis_devolvem_none(self):
        for linha in ("BTN SAS 1", "BTN FBW 1", "BTN AP 1", "ENC AP 1", "BTN POUSO", "ENC POUSO 1", "ENC SUB",
                      "ENC SUB x", "ENC SUB 1.5", "BTN SUB 2", "BTN SUB", "BTN EXEC 1", "SCR POUSO OFF"):
            self.assertIsNone(self.painel.tratar(linha, 0.0, "SUBIDA"), linha)
        self.assertEqual(self.menu.valores, {"ALT": 80, "INC": 0, "PLANO": 0})
        self.assertEqual(self.menu.cursor, 0)

    def test_sem_menu_as_linhas_da_subida_nao_sao_do_painel(self):
        painel = PainelScripts({"POUSO": self.pouso})
        self.assertIsNone(painel.tratar("ENC SUB 1", 0.0, "SUBIDA"))
        self.assertIsNone(painel.tratar("BTN SUB 1", 0.0, "SUBIDA"))
        self.assertEqual(painel.tela(), {})
        painel.sair_do_menu()

    def test_pagina_em_uso(self):
        self.assertIsNone(self.painel.pagina_em_uso(0.0))
        self.painel.tratar("BTN LANCAR 1", 0.0)
        self.assertEqual(self.painel.pagina_em_uso(1.0), "SUBIDA")
        self.painel.atualizar(SEGURAR)
        self.painel.tratar("BTN LANCAR 0", SEGURAR)
        self.assertEqual(self.painel.estado("LANCAR", SEGURAR), "ATIVO")
        self.assertEqual(self.painel.pagina_em_uso(SEGURAR), "SUBIDA")
        self.assertEqual(self.painel.luzes(SEGURAR)["SCR LANCAR"], "SCR LANCAR ATIVO")
        self.painel.tratar("BTN LANCAR 1", 20.0)
        self.painel.atualizar(20.0 + SEGURAR)
        self.painel.tratar("BTN LANCAR 0", 20.0 + SEGURAR)
        self.painel.atualizar(20.0 + SEGURAR)
        self.assertEqual(self.painel.estado("LANCAR", 20.0 + SEGURAR), "ABORT")
        self.assertEqual(self.painel.pagina_em_uso(20.0 + SEGURAR), "SUBIDA")
        self.assertIsNone(self.painel.pagina_em_uso(20.0 + SEGURAR + MOSTRA_FIM))

    def test_pagina_em_uso_do_pouso(self):
        self.painel.tratar("BTN POUSO 1", 0.0)
        self.painel.atualizar(SEGURAR)
        self.painel.tratar("BTN POUSO 0", SEGURAR)
        self.assertEqual(self.painel.pagina_em_uso(SEGURAR), "POUSO")

    def test_sair_do_menu_e_tela(self):
        self.painel.tratar("ENC SUB 1", 0.0, "SUBIDA")
        self.painel.tratar("BTN SUB 1", 1.0, "SUBIDA")
        self.painel.tratar("BTN SUB 0", 1.1, "SUBIDA")
        self.assertEqual(self.painel.tela()["SBC"], "SBC INC 1")
        self.painel.sair_do_menu()
        self.assertEqual(self.painel.tela()["SBC"], "SBC INC 0")
        self.assertEqual(self.painel.tela(), self.menu.linhas())

    def test_com_a_subida_voando_o_encoder_nao_mexe_no_menu(self):
        self.painel.tratar("BTN LANCAR 1", 0.0)
        self.painel.atualizar(SEGURAR)
        self.painel.tratar("BTN LANCAR 0", SEGURAR)
        self.assertEqual(self.painel.ativo(), "LANCAR")
        for linha in ("ENC SUB 1", "ENC SUB -3", "BTN SUB 1", "BTN SUB 0", "BTN SUB 1", "BTN SUB 0", "ENC SUB 1"):
            self.assertEqual(self.painel.tratar(linha, 10.0, "SUBIDA"), "SUBIDA", linha)
        self.assertEqual(self.menu.cursor, 0)
        self.assertFalse(self.menu.editando)
        self.assertEqual(self.menu.valores, {"ALT": 80, "INC": 0, "PLANO": 0})
        self.assertEqual(self.painel.tratar("ENC SUB 1", 10.0, "NAV"), "SUBIDA")

        self.lancar.terminar(subida.EM_ORBITA)
        self.painel.atualizar(30.0)
        self.assertIsNone(self.painel.ativo())
        self.assertEqual(self.painel.tratar("ENC SUB 1", 31.0, "SUBIDA"), "SUBIDA")
        self.assertEqual(self.menu.linha, "INC")

    def test_com_o_pouso_voando_o_encoder_da_subida_mexe_no_menu(self):
        self.painel.tratar("BTN POUSO 1", 0.0)
        self.painel.atualizar(SEGURAR)
        self.painel.tratar("BTN POUSO 0", SEGURAR)
        self.assertEqual(self.painel.ativo(), "POUSO")
        self.assertEqual(self.painel.tratar("ENC SUB 1", 10.0, "SUBIDA"), "SUBIDA")
        self.assertEqual(self.menu.linha, "INC")

    def test_um_script_por_vez_com_os_dois_korry(self):
        self.painel.tratar("BTN LANCAR 1", 0.0)
        self.painel.atualizar(SEGURAR)
        self.painel.tratar("BTN POUSO 1", 1.0)
        self.painel.atualizar(1.0 + SEGURAR)
        self.assertEqual(self.pouso.iniciado, 0)
        self.assertEqual(self.painel.ativo(), "LANCAR")

    def test_os_dois_scripts_tem_luzes(self):
        self.assertEqual(self.painel.luzes(0.0), {"SCR POUSO": "SCR POUSO OFF", "SCR LANCAR": "SCR LANCAR OFF"})


class LinhasFalsas:
    """Faz o papel da tela e do painel na ponte: guarda o que recebe e entrega as linhas combinadas."""

    def __init__(self):
        self.recebidas = []
        self.pendentes = []

    def enviar(self, linha):
        self.recebidas.append(linha)

    def linhas(self):
        entregues, self.pendentes = self.pendentes, []
        return entregues

    def com(self, prefixo):
        return [linha for linha in self.recebidas if linha.startswith(prefixo)]


class TestVoarComAPonteDaSubida(unittest.TestCase):
    """O voar do mfd.py ligando o painel de scripts, o menu da subida, a tela e o painel."""

    def setUp(self):
        self.tela = LinhasFalsas()
        self.painel = LinhasFalsas()
        self.menu = MenuSubida()
        self.lancar = ProcessoFalso()
        self.scripts = PainelScripts({"POUSO": ProcessoFalso(), "LANCAR": self.lancar}, self.menu)

    def voar(self, passos, tempo=10.0):
        """passos: lista de (linhas do painel, condição): manda as linhas e só passa ao próximo passo quando a condição vale."""
        limite = time.monotonic() + tempo
        andamento = {"passo": 0, "enviado": False}

        def continua_valida():
            if time.monotonic() > limite or andamento["passo"] >= len(passos):
                return False
            linhas, condicao = passos[andamento["passo"]]
            if not andamento["enviado"]:
                self.painel.pendentes.extend(linhas)
                andamento["enviado"] = True
            elif condicao():
                andamento["passo"] += 1
                andamento["enviado"] = False
            return True

        with mock.patch.object(mfd, "Scripts", lambda: Scripts(porta=0)), mock.patch.object(mfd, "VERIFICA_NAVE", 0.0):
            demo = mfd.Demo()
            try:
                mfd.voar(
                    self.tela, Transmissor(self.tela), demo, demo, continua_valida,
                    self.painel, Sistemas(None), self.scripts,
                )
            finally:
                demo.fechar()
        self.assertEqual(andamento["passo"], len(passos), "o voar não chegou ao fim dos passos")

    def test_korry_lancar_abre_a_pagina_subida_e_as_linhas_vao_cada_uma_para_o_seu_lado(self):
        self.voar([
            ([], lambda: "SCR LANCAR OFF" in self.tela.recebidas and "SBC ALT 0" in self.tela.recebidas),
            (["BTN LANCAR 1"], lambda: "PAG SUBIDA" in self.tela.recebidas and self.painel.com("SCR LANCAR LIGA")),
        ])
        self.assertLess(self.tela.recebidas.index("PAG NAV"), self.tela.recebidas.index("PAG SUBIDA"))
        self.assertEqual(self.painel.com("PAG"), [])
        for linha in ("SBV ALT 80", "SBV INC 0", "SBV PLANO 0", "SBC ALT 0"):
            self.assertIn(linha, self.tela.recebidas)
        self.assertEqual(self.painel.com("SBV"), [])
        self.assertEqual(self.painel.com("SBC"), [])
        self.assertIn("SCR LANCAR OFF", self.tela.recebidas)
        self.assertIn("SCR LANCAR OFF", self.painel.recebidas)
        self.assertTrue(self.tela.com("SCR LANCAR LIGA"))
        self.assertTrue(self.painel.com("SCR LANCAR LIGA"))
        self.assertIn("SUB OFF", self.tela.recebidas)
        self.assertEqual(self.painel.com("SUB"), [])

    def test_encoder_da_subida_primeiro_abre_a_pagina_e_depois_mexe_no_menu(self):
        self.voar([
            ([], lambda: "PAG NAV" in self.tela.recebidas),
            (["ENC SUB 1"], lambda: "PAG SUBIDA" in self.tela.recebidas),
            ([], lambda: self.menu.cursor == 0 and self.tela.com("SBC")[-1] == "SBC ALT 0"),
            (["ENC SUB 1"], lambda: "SBC INC 0" in self.tela.recebidas),
        ])
        self.assertEqual(self.menu.linha, "INC")
        self.assertEqual(self.tela.com("SBC")[0], "SBC ALT 0")
        self.assertEqual(self.tela.com("SBC")[-1], "SBC INC 0")
        self.assertEqual(self.menu.valores, {"ALT": 80, "INC": 0, "PLANO": 0})
        self.assertEqual(self.painel.com("SBC"), [])

    def test_a_tela_fora_da_subida_volta_a_fechar_o_menu(self):
        self.voar([
            (["ENC SUB 1"], lambda: "PAG SUBIDA" in self.tela.recebidas),
            (["ENC SUB 1", "BTN SUB 1", "BTN SUB 0"], lambda: "SBC INC 1" in self.tela.recebidas),
            (["BTN SAS_PRO 1"], lambda: "PAG SAS" in self.tela.recebidas and self.tela.com("SBC")[-1] == "SBC INC 0"),
        ])
        self.assertFalse(self.menu.editando)
        self.assertEqual(self.menu.linha, "INC")


class TestProcessoComArgumentos(unittest.TestCase):
    """Os argumentos podem ser uma função, chamada na hora de abrir o script."""

    def esperar_sair(self, processo):
        fim = time.monotonic() + 10
        while processo.rodando() and time.monotonic() < fim:
            time.sleep(0.02)
        self.assertFalse(processo.rodando())

    def test_valores_do_menu_na_hora_de_iniciar(self):
        menu = MenuSubida()
        with tempfile.TemporaryDirectory() as pasta:
            saida = os.path.join(pasta, "argumentos.json")
            script = os.path.join(pasta, "ecoar.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write("import json, sys\nwith open(sys.argv[1], 'w') as f:\n    json.dump(sys.argv[2:], f)\n")
            processo = Processo("LANCAR", lambda: [script, saida] + menu.argumentos())

            menu.valores.update({"ALT": 120, "INC": 45})
            processo.iniciar()
            self.esperar_sair(processo)
            with open(saida, encoding="utf-8") as f:
                self.assertEqual(json.load(f), ["--altitude", "120000", "--inclinacao", "45"])

            menu.valores.update({"ALT": 80, "INC": 98, "PLANO": 1})
            processo.iniciar()
            self.esperar_sair(processo)
            with open(saida, encoding="utf-8") as f:
                self.assertEqual(json.load(f), ["--altitude", "80000", "--inclinacao", "98", "--plano-do-alvo"])
            self.assertEqual(processo.codigo, 0)

    def test_lista_continua_valendo(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = os.path.join(pasta, "argumentos.json")
            script = os.path.join(pasta, "ecoar.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write("import json, sys\nwith open(sys.argv[1], 'w') as f:\n    json.dump(sys.argv[2:], f)\n")
            processo = Processo("POUSO", [script, saida, "--demo"])
            processo.iniciar()
            self.esperar_sair(processo)
            with open(saida, encoding="utf-8") as f:
                self.assertEqual(json.load(f), ["--demo"])


class TestLinhasDoPouso(unittest.TestCase):
    """O pouso.py manda as linhas POU; a ponte confere e repassa para a tela."""

    def setUp(self):
        self.ponte = Scripts(porta=0)
        self.porta = self.ponte._socket.getsockname()[1]
        self.enviar = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def tearDown(self):
        self.ponte.fechar()
        self.enviar.close()

    def esperar(self, condicao, tempo=2.0):
        fim = time.monotonic() + tempo
        while time.monotonic() < fim:
            if condicao():
                return True
            time.sleep(0.02)
        return False

    def test_linhas_cabem_e_passam(self):
        nave = pouso.NaveDemo()
        guiagem = pouso.Guiagem(nave.densidade)
        l = nave.leitura()
        acelerador, modo = guiagem.passo(l)
        linhas = pouso.linhas_de_estado(l, guiagem, acelerador, modo, "EMPUXO")
        for linha in linhas:
            self.assertLessEqual(len(linha), 31, linha)
        self.assertEqual(self.ponte.estado_pouso(), {"POU": "POU OFF"})
        self.enviar.sendto("\n".join(linhas).encode("ascii"), ("127.0.0.1", self.porta))
        self.assertTrue(self.esperar(lambda: "POU FASE" in self.ponte.estado_pouso()))
        estado = self.ponte.estado_pouso()
        self.assertEqual(sorted(estado.values()), sorted(linhas))
        self.assertEqual(estado["POU AVISO"], "POU AVISO EMPUXO")

    def test_linha_errada_e_descartada(self):
        self.enviar.sendto(b"POU FASE VOANDO\nPOU ALT muito", ("127.0.0.1", self.porta))
        time.sleep(0.1)
        self.assertEqual(self.ponte.estado_pouso(), {"POU": "POU OFF"})

    def test_o_pouso_nao_recebe_os_comandos_do_fbw(self):
        self.enviar.sendto(b"POU FASE QUEDA", ("127.0.0.1", self.porta))
        self.assertTrue(self.esperar(lambda: "POU FASE" in self.ponte.estado_pouso()))
        self.assertIsNone(self.ponte._endereco)


class TestLinhasDaSubida(unittest.TestCase):
    """O subida.py manda as linhas SUB; a ponte confere e repassa para a tela."""

    def setUp(self):
        self.ponte = Scripts(porta=0)
        self.porta = self.ponte._socket.getsockname()[1]
        self.enviar = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def tearDown(self):
        self.ponte.fechar()
        self.enviar.close()

    def esperar(self, condicao, tempo=2.0):
        fim = time.monotonic() + tempo
        while time.monotonic() < fim:
            if condicao():
                return True
            time.sleep(0.02)
        return False

    def linhas_da_nave(self):
        nave = subida.NaveSimulada.kerbin()
        guiagem = subida.Guiagem(subida.KERBIN, 80_000.0, 0.0, ler_estagios=nave.estagios)
        l = nave.leitura()
        guiagem.passo(l)
        return subida.linhas_de_estado(l, guiagem, subida.KERBIN)

    def test_linhas_cabem_e_passam(self):
        linhas = self.linhas_da_nave()
        for linha in linhas:
            self.assertLessEqual(len(linha), 31, linha)
            self.assertTrue(linha.isascii(), linha)
        self.assertEqual(self.ponte.estado_subida(), {"SUB": "SUB OFF"})
        self.enviar.sendto("\n".join(linhas).encode("ascii"), ("127.0.0.1", self.porta))
        self.assertTrue(self.esperar(lambda: "SUB FASE" in self.ponte.estado_subida()))
        estado = self.ponte.estado_subida()
        self.assertEqual(sorted(estado.values()), sorted(linhas))
        self.assertEqual(estado["SUB FASE"], "SUB FASE DECOLAGEM")
        self.assertEqual(estado["SUB ALVO"], "SUB ALVO 80000")
        self.assertEqual(estado["SUB AVISO"], "SUB AVISO OFF")

    def test_as_fases_e_os_avisos_do_script_passam(self):
        fases = [getattr(subida, nome) for nome in (
            "JANELA", "DECOLAGEM", "GIRO", "CURVA", "VACUO", "COSTA", "CIRCULARIZA", "PLANO", "ORBITA", "FALHA")]
        avisos = [getattr(subida, nome) for nome in (
            "AVISO_EMPUXO", "AVISO_ALTITUDE", "AVISO_INCLINACAO", "AVISO_ALVO", "AVISO_COMBUSTIVEL")]
        self.assertEqual(sorted(CAMPOS_SUBIDA["FASE"]), sorted(fases))
        self.assertEqual(sorted(CAMPOS_SUBIDA["AVISO"]), sorted(avisos + ["OFF"]))
        pacote = [f"SUB FASE {fase}" for fase in fases] + [f"SUB AVISO {aviso}" for aviso in avisos]
        self.enviar.sendto("\n".join(pacote).encode("ascii"), ("127.0.0.1", self.porta))
        self.assertTrue(self.esperar(lambda: "SUB AVISO" in self.ponte.estado_subida()))
        self.assertEqual(self.ponte.estado_subida()["SUB AVISO"], f"SUB AVISO {avisos[-1]}")

    def test_valores_off_passam(self):
        pacote = ["SUB AP OFF", "SUB PE OFF", "SUB JAN OFF", "SUB GIRO OFF", "SUB PE -123456"]
        self.enviar.sendto("\n".join(pacote).encode("ascii"), ("127.0.0.1", self.porta))
        self.assertTrue(self.esperar(lambda: "SUB GIRO" in self.ponte.estado_subida()))
        estado = self.ponte.estado_subida()
        self.assertEqual(estado["SUB AP"], "SUB AP OFF")
        self.assertEqual(estado["SUB PE"], "SUB PE -123456")

    def test_linha_errada_e_descartada(self):
        pacote = [
            "SUB FASE VOANDO", "SUB ALT muito", "SUB OFF", "SUB ALT", "SUB ALT 1 2", "SUB XIS 1",
            "SUB MOTOR OFF", "SUB AVISO NADA", "SUB AP 1.5",
        ]
        self.enviar.sendto("\n".join(pacote).encode("ascii"), ("127.0.0.1", self.porta))
        time.sleep(0.1)
        self.assertEqual(self.ponte.estado_subida(), {"SUB": "SUB OFF"})

    def test_sem_noticia_volta_a_off(self):
        self.enviar.sendto(b"SUB FASE GIRO", ("127.0.0.1", self.porta))
        self.assertTrue(self.esperar(lambda: "SUB FASE" in self.ponte.estado_subida()))
        self.ponte._quando_subida -= 2.0
        self.assertEqual(self.ponte.estado_subida(), {"SUB": "SUB OFF"})
        self.assertEqual(self.ponte.estado_subida(), {"SUB": "SUB OFF"})

    def test_a_subida_nao_recebe_os_comandos_do_fbw(self):
        self.enviar.sendto(b"SUB FASE GIRO", ("127.0.0.1", self.porta))
        self.assertTrue(self.esperar(lambda: "SUB FASE" in self.ponte.estado_subida()))
        self.assertIsNone(self.ponte._endereco)

    def test_o_endereco_do_fbw_nao_muda(self):
        fbw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        fbw.bind(("127.0.0.1", 0))
        try:
            fbw.sendto(b"FBW OFF", ("127.0.0.1", self.porta))

            def endereco_do_fbw():
                self.ponte.estado_fbw()
                return self.ponte._endereco

            self.assertTrue(self.esperar(lambda: endereco_do_fbw() is not None))
            endereco = self.ponte._endereco
            self.assertEqual(endereco, fbw.getsockname())
            self.enviar.sendto(b"SUB FASE GIRO", ("127.0.0.1", self.porta))
            self.assertTrue(self.esperar(lambda: "SUB FASE" in self.ponte.estado_subida()))
            self.assertEqual(self.ponte._endereco, endereco)
        finally:
            fbw.close()


class TestProcessoDeVerdade(unittest.TestCase):
    """O pouso.py --demo aberto pela ponte, mandando por UDP, e abortado pelo korry."""

    def test_abrir_e_abortar(self):
        ponte = Scripts(porta=0)
        porta = ponte._socket.getsockname()[1]
        processo = painel_scripts.processo_pouso("127.0.0.1", demo=True, tela=f"127.0.0.1:{porta}")
        painel = PainelScripts({"POUSO": processo})
        try:
            painel.tratar("BTN POUSO 1", 0.0)
            painel.atualizar(SEGURAR)
            painel.tratar("BTN POUSO 0", SEGURAR)
            self.assertEqual(painel.estado("POUSO", SEGURAR), "ATIVO")
            fim = time.monotonic() + 10
            while "POU FASE" not in ponte.estado_pouso() and time.monotonic() < fim:
                time.sleep(0.05)
            self.assertIn(ponte.estado_pouso()["POU FASE"], ("POU FASE QUEDA", "POU FASE QUEIMA"))

            painel.tratar("BTN POUSO 1", 100.0)
            painel.atualizar(100.0 + SEGURAR)
            fim = time.monotonic() + 10
            while processo.rodando() and time.monotonic() < fim:
                time.sleep(0.05)
            painel.atualizar(106.0)
            self.assertEqual(painel.estado("POUSO", 106.0), "ABORT")
            self.assertEqual(processo.codigo, pouso.INTERROMPIDO)
        finally:
            processo.fechar()
            ponte.fechar()

    def test_subida_abrir_e_abortar(self):
        ponte = Scripts(porta=0)
        porta = ponte._socket.getsockname()[1]
        menu = MenuSubida()
        menu.valores.update({"ALT": 100, "INC": 0})
        processo = painel_scripts.processo_subida("127.0.0.1", menu, demo=True, tela=f"127.0.0.1:{porta}")
        painel = PainelScripts({"LANCAR": processo}, menu)
        try:
            painel.tratar("BTN LANCAR 1", 0.0)
            painel.atualizar(SEGURAR)
            painel.tratar("BTN LANCAR 0", SEGURAR)
            self.assertEqual(painel.estado("LANCAR", SEGURAR), "ATIVO")
            fim = time.monotonic() + 20
            while "SUB FASE" not in ponte.estado_subida() and time.monotonic() < fim:
                time.sleep(0.05)
            estado = ponte.estado_subida()
            self.assertIn(estado["SUB FASE"], ("SUB FASE DECOLAGEM", "SUB FASE GIRO", "SUB FASE CURVA"))
            self.assertEqual(estado["SUB ALVO"], "SUB ALVO 100000")

            painel.tratar("BTN LANCAR 1", 100.0)
            painel.atualizar(100.0 + SEGURAR)
            fim = time.monotonic() + 10
            while processo.rodando() and time.monotonic() < fim:
                time.sleep(0.05)
            painel.atualizar(106.0)
            self.assertEqual(painel.estado("LANCAR", 106.0), "ABORT")
            self.assertEqual(processo.codigo, subida.INTERROMPIDO)
        finally:
            processo.fechar()
            ponte.fechar()

    def test_script_que_nao_existe_falha(self):
        painel = PainelScripts({"POUSO": Processo("POUSO", ["nao_existe.py"])})
        painel.tratar("BTN POUSO 1", 0.0)
        painel.atualizar(SEGURAR)
        fim = time.monotonic() + 10
        while painel.processos["POUSO"].rodando() and time.monotonic() < fim:
            time.sleep(0.05)
        painel.atualizar(SEGURAR + 1)
        self.assertEqual(painel.estado("POUSO", SEGURAR + 1), "FALHA")


if __name__ == "__main__":
    unittest.main()
