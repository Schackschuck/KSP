"""Testes do encoder AJUSTE (ajuste.py), sem o Uno e sem serial.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_ajuste.py
    python bridge/tests/test_ajuste.py -v
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import serial

import ajuste
from ajuste import Ajuste, EncoderSerial, destino


class RelogioFalso:
    def __init__(self):
        self.agora = 100.0

    def __call__(self):
        return self.agora


class PortaFalsa:
    """Faz o papel do ponte.Painel: linhas() devolve o que estava pendente."""

    def __init__(self, pendentes=(), erro=None):
        self.pendentes = list(pendentes)
        self.erro = erro
        self.fechada = 0

    def linhas(self):
        if self.erro is not None:
            raise self.erro
        lidas, self.pendentes = self.pendentes, []
        return lidas

    def fechar(self):
        self.fechada += 1


class AbridorFalso:
    """Faz o papel da classe que abre a porta: cada chamada usa o próximo resultado da lista."""

    def __init__(self, resultados):
        self.resultados = list(resultados)
        self.chamadas = []

    def __call__(self, porta):
        self.chamadas.append(porta)
        resultado = self.resultados.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


class TestDestino(unittest.TestCase):
    def test_subida_vai_para_o_menu_da_subida(self):
        self.assertEqual(destino("SUBIDA"), "SUB")

    def test_qualquer_outra_pagina_vai_para_o_piloto_automatico(self):
        for pagina in ("NAV", "AP", "SAS", "POUSO"):
            with self.subTest(pagina=pagina):
                self.assertEqual(destino(pagina), "AP")


class TestTraduzir(unittest.TestCase):
    def setUp(self):
        self.ajuste = Ajuste()

    def test_giro_positivo_e_negativo(self):
        self.assertEqual(self.ajuste.traduzir("ENC AJUSTE 3", "NAV"), "ENC AP 3")
        self.assertEqual(self.ajuste.traduzir("ENC AJUSTE -2", "NAV"), "ENC AP -2")
        self.assertEqual(self.ajuste.traduzir("ENC AJUSTE +4", "SUBIDA"), "ENC SUB 4")
        self.assertEqual(self.ajuste.traduzir("ENC AJUSTE -1", "SUBIDA"), "ENC SUB -1")

    def test_aperto_e_soltura(self):
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 1", "NAV"), "BTN AP 1")
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 0", "NAV"), "BTN AP 0")
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 1", "SUBIDA"), "BTN SUB 1")
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 0", "SUBIDA"), "BTN SUB 0")

    def test_linhas_que_nao_sao_do_ajuste(self):
        for linha in ("READY", "", "ENC AP 1", "BTN STAGE 1", "ENC AJUSTE", "ENC AJUSTE 1 2"):
            with self.subTest(linha=linha):
                self.assertIsNone(self.ajuste.traduzir(linha, "NAV"))

    def test_valores_invalidos(self):
        self.assertIsNone(self.ajuste.traduzir("ENC AJUSTE x", "NAV"))
        self.assertIsNone(self.ajuste.traduzir("ENC AJUSTE 1.5", "NAV"))
        self.assertIsNone(self.ajuste.traduzir("BTN AJUSTE 2", "NAV"))
        self.assertIsNone(self.ajuste.traduzir("BTN AJUSTE x", "NAV"))

    def test_soltura_vai_para_onde_foi_o_aperto(self):
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 1", "SUBIDA"), "BTN SUB 1")
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 0", "AP"), "BTN SUB 0")

    def test_soltura_sem_aperto_vai_para_a_pagina(self):
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 0", "SUBIDA"), "BTN SUB 0")
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 0", "NAV"), "BTN AP 0")

    def test_soltura_esquece_o_aperto(self):
        self.ajuste.traduzir("BTN AJUSTE 1", "SUBIDA")
        self.ajuste.traduzir("BTN AJUSTE 0", "SUBIDA")
        self.assertEqual(self.ajuste.traduzir("BTN AJUSTE 0", "NAV"), "BTN AP 0")


class TestEncoderSerial(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.saida = io.StringIO()
        self.silencio = contextlib.redirect_stdout(self.saida)
        self.silencio.__enter__()
        self.addCleanup(self.silencio.__exit__, None, None, None)

    def criar(self, resultados):
        abridor = AbridorFalso(resultados)
        return EncoderSerial("COM8", abridor, self.relogio), abridor

    def test_abre_na_hora_e_devolve_as_linhas(self):
        porta = PortaFalsa(["READY", "ENC AJUSTE 1"])
        encoder, abridor = self.criar([porta])
        self.assertEqual(abridor.chamadas, ["COM8"])
        self.assertEqual(encoder.linhas(), ["READY", "ENC AJUSTE 1"])
        self.assertEqual(encoder.linhas(), [])
        self.assertIn("Encoder AJUSTE em COM8.", self.saida.getvalue())

    def test_primeira_abertura_falha_e_reabre_depois_de_reabrir(self):
        porta = PortaFalsa(["ENC AJUSTE 2"])
        encoder, abridor = self.criar([serial.SerialException("sem porta"), porta])
        self.assertIn("Não foi possível abrir o encoder em COM8", self.saida.getvalue())
        self.assertEqual(encoder.linhas(), [])
        self.relogio.agora += ajuste.REABRIR - 0.1
        self.assertEqual(encoder.linhas(), [])
        self.assertEqual(len(abridor.chamadas), 1)
        self.relogio.agora += 0.2
        self.assertEqual(encoder.linhas(), ["ENC AJUSTE 2"])
        self.assertEqual(len(abridor.chamadas), 2)

    def test_o_erro_de_abertura_e_avisado_uma_vez(self):
        encoder, abridor = self.criar([OSError("a"), OSError("b"), OSError("c"), PortaFalsa()])
        for _ in range(2):
            self.relogio.agora += ajuste.REABRIR
            self.assertEqual(encoder.linhas(), [])
        self.assertEqual(len(abridor.chamadas), 3)
        self.assertEqual(self.saida.getvalue().count("Não foi possível abrir o encoder"), 1)

    def test_porta_que_cai_devolve_vazio_e_reabre_depois(self):
        caida = PortaFalsa(erro=serial.SerialException("cabo solto"))
        nova = PortaFalsa(["BTN AJUSTE 1"])
        encoder, abridor = self.criar([caida, nova])
        self.assertEqual(encoder.linhas(), [])
        self.assertEqual(caida.fechada, 1)
        self.assertIn("O encoder foi desconectado", self.saida.getvalue())
        self.assertEqual(encoder.linhas(), [])
        self.assertEqual(len(abridor.chamadas), 1)
        self.relogio.agora += ajuste.REABRIR
        self.assertEqual(encoder.linhas(), ["BTN AJUSTE 1"])
        self.assertEqual(len(abridor.chamadas), 2)

    def test_porta_que_cai_com_oserror(self):
        caida = PortaFalsa(erro=OSError("erro de E/S"))
        encoder, _ = self.criar([caida])
        self.assertEqual(encoder.linhas(), [])
        self.assertEqual(caida.fechada, 1)

    def test_fechar_sem_porta_aberta_nao_levanta(self):
        encoder, _ = self.criar([serial.SerialException("sem porta")])
        encoder.fechar()
        encoder.fechar()

    def test_fechar_fecha_a_porta(self):
        porta = PortaFalsa()
        encoder, _ = self.criar([porta])
        encoder.fechar()
        self.assertEqual(porta.fechada, 1)
        self.assertEqual(encoder.linhas(), [])

    def test_fechar_ignora_erro_da_porta(self):
        class PortaTeimosa(PortaFalsa):
            def fechar(self):
                raise serial.SerialException("já caiu")

        encoder, _ = self.criar([PortaTeimosa()])
        encoder.fechar()


if __name__ == "__main__":
    unittest.main()
