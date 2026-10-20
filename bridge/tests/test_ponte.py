"""Testes da reconexão da ponte (ponte.py), sem o KSP e sem serial.

Uso, a partir da raiz do repositório:
    python bridge/tests/test_ponte.py
    python bridge/tests/test_ponte.py -v
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import serial

import ponte


class DispositivoFalso:
    """Faz o papel do painel ou da tela: linhas() devolve o que estava pendente."""

    def __init__(self, pendentes=()):
        self.pendentes = list(pendentes)
        self.chamadas = 0

    def linhas(self):
        self.chamadas += 1
        lidas, self.pendentes = self.pendentes, []
        return lidas


class NaveFalsa:
    pass


class SpaceCenterFalso:
    def __init__(self, conexao):
        self._conexao = conexao

    @property
    def active_vessel(self):
        if self._conexao.excecoes:
            raise self._conexao.excecoes.pop(0)
        return self._conexao.nave


class ConexaoFalsa:
    """Faz o papel da conexão com o kRPC."""

    def __init__(self, excecoes=()):
        self.excecoes = list(excecoes)
        self.nave = NaveFalsa()
        self.space_center = SpaceCenterFalso(self)
        self.fechada = 0

    def close(self):
        self.fechada += 1


class ConectorFalso:
    """Faz o papel do krpc.connect: levanta as exceções da lista e depois devolve conexões."""

    def __init__(self, excecoes=()):
        self.excecoes = list(excecoes)
        self.chamadas = 0
        self.conexoes = []

    def __call__(self, *args, **kwargs):
        self.chamadas += 1
        if self.excecoes:
            raise self.excecoes.pop(0)
        conexao = ConexaoFalsa()
        self.conexoes.append(conexao)
        return conexao


class TestPonte(unittest.TestCase):
    def setUp(self):
        self.connect_original = ponte.krpc.connect
        self.intervalo_original = ponte.INTERVALO_RECONEXAO
        ponte.INTERVALO_RECONEXAO = 0

    def tearDown(self):
        ponte.krpc.connect = self.connect_original
        ponte.INTERVALO_RECONEXAO = self.intervalo_original

    def trocar_connect(self, excecoes=()):
        conector = ConectorFalso(excecoes)
        ponte.krpc.connect = conector
        return conector

    def test_conectar_tenta_de_novo_ate_o_jogo_abrir(self):
        conector = self.trocar_connect([ConnectionRefusedError(), ConnectionRefusedError()])
        dispositivo = DispositivoFalso(["BTN STAGE 1"])
        with contextlib.redirect_stdout(io.StringIO()):
            conn = ponte.conectar_krpc("192.168.50.1", dispositivo)
        self.assertIs(conn, conector.conexoes[0])
        self.assertEqual(conector.chamadas, 3)
        self.assertEqual(dispositivo.pendentes, [])
        self.assertGreaterEqual(dispositivo.chamadas, 2)

    def test_cada_motivo_e_avisado_uma_vez(self):
        self.trocar_connect([
            ConnectionRefusedError(),
            ConnectionRefusedError(),
            ConnectionRefusedError(),
            OSError("No route to host"),
        ])
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ponte.conectar_krpc("192.168.50.1", DispositivoFalso())
        texto = saida.getvalue()
        self.assertEqual(texto.count("recusou a conexão"), 1)
        self.assertEqual(texto.count("Não foi possível alcançar"), 1)
        self.assertIn("No route to host", texto)
        self.assertEqual(texto.count("Conectado ao kRPC."), 1)

    def test_manter_krpc_reconecta_quando_o_jogo_fecha(self):
        conector = self.trocar_connect()
        chamadas = []

        def acompanhar(conn, nave):
            chamadas.append((conn, nave))
            if len(chamadas) == 1:
                raise OSError("Connection closed")
            raise KeyboardInterrupt

        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            with self.assertRaises(KeyboardInterrupt):
                ponte.manter_krpc("192.168.50.1", [DispositivoFalso()], acompanhar)
        self.assertEqual(len(conector.conexoes), 2)
        self.assertEqual([c.fechada for c in conector.conexoes], [1, 1])
        self.assertIs(chamadas[0][0], conector.conexoes[0])
        self.assertIs(chamadas[1][0], conector.conexoes[1])
        self.assertIn("A conexão com o kRPC caiu", saida.getvalue())

    def test_manter_krpc_deixa_a_serial_exception_sair(self):
        conector = self.trocar_connect()

        def acompanhar(conn, nave):
            raise serial.SerialException("painel desconectado")

        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            with self.assertRaises(serial.SerialException):
                ponte.manter_krpc("192.168.50.1", [DispositivoFalso()], acompanhar)
        self.assertEqual(len(conector.conexoes), 1)
        self.assertEqual(conector.conexoes[0].fechada, 1)
        self.assertNotIn("A conexão com o kRPC caiu", saida.getvalue())

    def test_esperar_nave_descarta_o_que_os_dispositivos_mandam(self):
        conn = ConexaoFalsa([ValueError("fora da cena de voo")])
        painel = DispositivoFalso(["BTN STAGE 1"])
        tela = DispositivoFalso(["BTN STAGE 1"])
        with contextlib.redirect_stdout(io.StringIO()):
            nave = ponte.esperar_nave(conn, painel, tela)
        self.assertIs(nave, conn.nave)
        self.assertEqual(painel.pendentes, [])
        self.assertEqual(tela.pendentes, [])
        self.assertGreaterEqual(painel.chamadas, 1)
        self.assertGreaterEqual(tela.chamadas, 1)


if __name__ == "__main__":
    unittest.main()
