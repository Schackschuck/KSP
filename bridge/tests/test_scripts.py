"""Testes do painel de scripts (painel_scripts.py e a parte dele em mfd.py), sem o KSP.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_scripts.py
    python bridge/tests/test_scripts.py -v
"""

import os
import socket
import sys
import time
import unittest

# A ponte fica na pasta de cima (bridge/).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import painel_scripts
import sistemas
from mfd import Scripts
from painel_scripts import MOSTRA_FIM, SEGURAR, PainelScripts, Processo
from sistemas import Sistemas

# O pouso fica em scripts/, ao lado de bridge/.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import pouso  # noqa: E402


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
