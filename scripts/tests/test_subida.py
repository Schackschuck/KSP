"""Testes da subida automática (subida.py), sem o KSP.

As contas (elementos da órbita, plano do lançamento, rumo, janela, nó, tempo
de queima, simulação do giro) são testadas uma a uma. Os voos usam a
NaveSimulada do próprio subida.py, num referencial inercial destro com o
planeta girando por baixo, e a mesma Guiagem do script a 10 Hz, até ORBITA ou
FALHA (com limite de tempo de jogo e de passos, para não travar).

Uso, a partir da raiz do repositório:
    python scripts/tests/test_subida.py
    python scripts/tests/test_subida.py -v    # uma linha por teste
"""

import argparse
import contextlib
import dataclasses
import io
import math
import os
import re
import socket
import sys
import threading
import time
import types
import unittest
from dataclasses import dataclass
from time import sleep as dormir
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import subida
from subida import (
    COSTA,
    DECOLAGEM,
    FALHA,
    JANELA,
    KERBIN,
    MUN,
    ORBITA,
    PLANO,
    Comando,
    EstadoSim,
    Guiagem,
    NaveSimulada,
    angulo,
    cruz,
    elementos,
    esc,
    escolher_giro,
    inclinacao_de,
    plano_com_janela,
    plano_do_lancamento,
    plano_pela_posicao,
    ponto,
    proxima_janela,
    rotacionar,
    rumo_do_plano,
    simular,
    soma,
    tempo_de_queima,
    unit,
)

DT = 0.1
T_MAX_JOGO = 4 * 3600.0
PASSOS_MAX = 200_000


@dataclass
class Resultado:
    nave: object
    guiagem: object
    fases: list
    comandos_de_estagio: int
    ap: float
    pe: float
    inclinacao: float

    @property
    def fase(self):
        return self.guiagem.fase

    @property
    def dv(self):
        return self.guiagem.dv

    def erro_de_plano(self, n):
        l = self.nave.leitura()
        return angulo(unit(cruz(l.r, l.v)), n)


def voar(nave, guiagem):
    """Roda a guiagem a 10 Hz na nave simulada, até ORBITA, FALHA ou o limite."""
    fases = []
    estagios = 0
    for _ in range(PASSOS_MAX):
        comando = guiagem.passo(nave.leitura())
        if not fases or fases[-1] != guiagem.fase:
            fases.append(guiagem.fase)
        estagios += int(comando.estagiar)
        if guiagem.fase in (ORBITA, FALHA) or nave.t > T_MAX_JOGO:
            break
        nave.executar(comando)
        nave.avancar(DT)
    l = nave.leitura()
    corpo = nave.corpo
    _, _, ra, rp = elementos(corpo, l.r, l.v)
    return Resultado(
        nave=nave,
        guiagem=guiagem,
        fases=fases,
        comandos_de_estagio=estagios,
        ap=ra - corpo.raio,
        pe=rp - corpo.raio,
        inclinacao=inclinacao_de(corpo, l.r, l.v),
    )


def subir_de_kerbin(altitude, inclinacao, latitude=subida.LATITUDE_KSC, n_alvo=None, estagios=None, aceso=False):
    if estagios is None:
        nave = NaveSimulada.kerbin(latitude=latitude, longitude=0.0, aceso=aceso)
    else:
        nave = NaveSimulada(KERBIN, estagios, subida.AREA_FOGUETE_KERBIN, latitude, 0.0, aceso)
    guiagem = Guiagem(KERBIN, altitude, inclinacao, n_alvo=n_alvo, ler_estagios=nave.estagios)
    return voar(nave, guiagem)


def estagios_kerbin(combustivel_baixo, combustivel_cima):
    """O foguete de Kerbin com outro combustível em cada estágio, com as massas coerentes."""
    baixo, cima = [dataclasses.replace(e) for e in subida.FOGUETE_KERBIN]
    cima = dataclasses.replace(
        cima, combustivel=combustivel_cima, massa_inicial=cima.seca_solta + combustivel_cima
    )
    baixo = dataclasses.replace(
        baixo,
        combustivel=combustivel_baixo,
        massa_inicial=baixo.seca_solta + combustivel_baixo + cima.massa_inicial,
    )
    return [baixo, cima]


class TestVetores(unittest.TestCase):
    def test_produto_vetorial_e_destro(self):
        self.assertEqual(cruz((1, 0, 0), (0, 1, 0)), (0, 0, 1))
        self.assertEqual(cruz((0, 1, 0), (0, 0, 1)), (1, 0, 0))

    def test_unit_do_vetor_nulo_continua_nulo(self):
        self.assertEqual(unit((0.0, 0.0, 0.0)), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(subida.norma(unit((3.0, 4.0, 12.0))), 1.0)

    def test_angulo_limita_o_acos(self):
        self.assertAlmostEqual(angulo((1, 0, 0), (1, 0, 0)), 0.0)
        self.assertAlmostEqual(angulo((1, 0, 0), (-2, 0, 0)), 180.0)
        self.assertAlmostEqual(angulo((1, 0, 0), (0, 5, 0)), 90.0)
        self.assertEqual(angulo((0, 0, 0), (1, 0, 0)), 0.0)


class TestContas(unittest.TestCase):
    def test_elementos_de_uma_orbita_circular(self):
        r = KERBIN.raio + 80_000.0
        v = math.sqrt(KERBIN.mu / r)
        a, e, ra, rp = elementos(KERBIN, (r, 0.0, 0.0), (0.0, 0.0, -v))
        self.assertAlmostEqual(a, r, delta=1.0)
        self.assertLess(e, 1e-6)
        self.assertAlmostEqual(ra, r, delta=1.0)
        self.assertAlmostEqual(rp, r, delta=1.0)

    def test_elementos_de_uma_orbita_eliptica(self):
        rp = KERBIN.raio + 50_000.0
        ra = KERBIN.raio + 200_000.0
        a = (rp + ra) / 2.0
        e = (ra - rp) / (ra + rp)
        vp = math.sqrt(KERBIN.mu * (2.0 / rp - 1.0 / a))
        for nome, r, v in (
            ("periastro", (rp, 0.0, 0.0), (0.0, 0.0, -vp)),
            ("apoastro", (ra, 0.0, 0.0), (0.0, 0.0, -vp * rp / ra)),
        ):
            with self.subTest(ponto=nome):
                a_, e_, ra_, rp_ = elementos(KERBIN, r, v)
                self.assertAlmostEqual(a_, a, delta=1.0)
                self.assertAlmostEqual(e_, e, places=6)
                self.assertAlmostEqual(ra_, ra, delta=1.0)
                self.assertAlmostEqual(rp_, rp, delta=1.0)

    def test_elementos_no_meio_da_orbita_eliptica(self):
        rp = KERBIN.raio + 50_000.0
        ra = KERBIN.raio + 200_000.0
        a = (rp + ra) / 2.0
        e = (ra - rp) / (ra + rp)
        p = a * (1.0 - e * e)
        v_t = math.sqrt(KERBIN.mu / p)
        v_r = v_t * e
        _, e_, ra_, rp_ = elementos(KERBIN, (p, 0.0, 0.0), (v_r, v_t, 0.0))
        self.assertAlmostEqual(e_, e, places=6)
        self.assertAlmostEqual(ra_, ra, delta=1.0)
        self.assertAlmostEqual(rp_, rp, delta=1.0)

    def test_elementos_de_escape_tem_apoastro_infinito(self):
        r = KERBIN.raio + 100_000.0
        v = 1.5 * math.sqrt(2.0 * KERBIN.mu / r)
        a, e, ra, rp = elementos(KERBIN, (r, 0.0, 0.0), (0.0, 0.0, -v))
        self.assertTrue(math.isinf(ra))
        self.assertTrue(math.isinf(a))
        self.assertGreater(e, 1.0)
        self.assertAlmostEqual(rp, r, delta=1.0)

    def test_tempo_de_queima_confere_com_a_integracao_passo_a_passo(self):
        massa, empuxo, isp, dv = 10_000.0, 50_000.0, 300.0, 1_000.0
        ve = isp * subida.G0
        m, v, t, dt = massa, 0.0, 0.0, 0.001
        while v < dv:
            v += empuxo / m * dt
            m -= empuxo / ve * dt
            t += dt
        self.assertAlmostEqual(tempo_de_queima(dv, massa, empuxo, isp), t, delta=0.05)

    def test_tempo_de_queima_pequeno_vira_dv_vezes_massa_sobre_empuxo(self):
        self.assertAlmostEqual(tempo_de_queima(0.01, 10_000.0, 50_000.0, 300.0), 0.01 * 10_000.0 / 50_000.0, places=6)

    def test_tempo_de_queima_sem_empuxo_e_infinito(self):
        self.assertTrue(math.isinf(tempo_de_queima(100.0, 1_000.0, 0.0, 300.0)))
        self.assertTrue(math.isinf(tempo_de_queima(100.0, 1_000.0, 1_000.0, 0.0)))

    def test_acelerador_pela_pressao_dinamica(self):
        self.assertEqual(subida.acel_q(0.0), 1.0)
        self.assertEqual(subida.acel_q(subida.Q_MAX), 1.0)
        self.assertAlmostEqual(subida.acel_q(subida.Q_MAX + subida.Q_FAIXA / 2), 0.5)
        self.assertEqual(subida.acel_q(1e9), subida.ACEL_Q_MIN)

    def test_acelerador_pelo_corte_no_apoastro(self):
        alvo = 80_000.0
        self.assertEqual(subida.acel_corte(alvo, alvo), 0.0)
        self.assertEqual(subida.acel_corte(alvo + 1.0, alvo), 0.0)
        self.assertEqual(subida.acel_corte(0.0, alvo), 1.0)
        self.assertAlmostEqual(subida.acel_corte(alvo - 2_500.0, alvo), 0.5)
        self.assertEqual(subida.acel_corte(alvo - 1.0, alvo), subida.ACEL_MIN)

    def test_empuxo_e_isp_pela_pressao(self):
        estagio = subida.FOGUETE_KERBIN[0]
        self.assertEqual(subida.empuxo_em(estagio, 0.0), estagio.empuxo_vacuo)
        self.assertEqual(subida.empuxo_em(estagio, 1.0), estagio.empuxo_mar)
        meio = subida.empuxo_em(estagio, 0.5)
        self.assertAlmostEqual(meio, (estagio.empuxo_vacuo + estagio.empuxo_mar) / 2)
        self.assertEqual(subida.isp_em(estagio, 0.0), estagio.isp_vacuo)
        self.assertEqual(subida.isp_em(estagio, 1.0), estagio.isp_mar)
        cima = subida.FOGUETE_KERBIN[1]
        self.assertEqual(subida.empuxo_em(cima, 100.0), 0.0)
        self.assertEqual(subida.isp_em(cima, 100.0), 1.0)

    def test_tempo_ate_o_apoastro(self):
        rp = KERBIN.raio + 80_000.0
        ra = KERBIN.raio + 300_000.0
        a = (rp + ra) / 2.0
        vp = math.sqrt(KERBIN.mu * (2.0 / rp - 1.0 / a))
        meia_volta = math.pi * math.sqrt(a**3 / KERBIN.mu)
        self.assertAlmostEqual(
            subida.tempo_ate_apoastro(KERBIN, (rp, 0.0, 0.0), (0.0, 0.0, -vp)), meia_volta, delta=0.01
        )
        nave = NaveSimulada.kerbin()
        nave.pousada = False
        nave.r, nave.v = (rp, 0.0, 0.0), (0.0, 0.0, -vp)
        nave.executar(Comando(acelerar_ate=meia_volta - 100.0))
        self.assertAlmostEqual(subida.tempo_ate_apoastro(KERBIN, nave.r, nave.v), 100.0, delta=0.5)

    def test_no_relativo_com_o_plano_do_equador(self):
        r = KERBIN.raio + 80_000.0
        v = math.sqrt(KERBIN.mu / r)
        i = math.radians(10.0)
        posicao, velocidade = (r, 0.0, 0.0), (0.0, v * math.sin(i), -v * math.cos(i))
        n_atual = unit(cruz(posicao, velocidade))
        movimento = math.sqrt(KERBIN.mu / r**3)
        espera, linha = subida.no_relativo(KERBIN, posicao, velocidade, KERBIN.polo)
        self.assertAlmostEqual(espera, 0.0, delta=0.01)
        self.assertAlmostEqual(abs(ponto(linha, (1.0, 0.0, 0.0))), 1.0, places=6)
        angulo_andado = 0.4
        posicao2 = rotacionar(posicao, n_atual, angulo_andado)
        velocidade2 = rotacionar(velocidade, n_atual, angulo_andado)
        espera, _ = subida.no_relativo(KERBIN, posicao2, velocidade2, KERBIN.polo)
        self.assertAlmostEqual(espera, (math.pi - angulo_andado) / movimento, delta=1.0)


class TestPlano(unittest.TestCase):
    def test_plano_do_lancamento_no_equador_com_45_graus(self):
        l = NaveSimulada.kerbin(latitude=0.0, longitude=0.0).leitura()
        n, usada = plano_do_lancamento(l, KERBIN, 45.0)
        self.assertAlmostEqual(math.degrees(math.acos(ponto(n, KERBIN.polo))), 45.0, delta=0.01)
        self.assertAlmostEqual(usada, 45.0, delta=0.01)

    def test_plano_do_lancamento_retrogrado_e_polar(self):
        l = NaveSimulada.kerbin(latitude=0.0, longitude=0.0).leitura()
        for pedida in (90.0, 120.0, 180.0):
            with self.subTest(inclinacao=pedida):
                n, usada = plano_do_lancamento(l, KERBIN, pedida)
                self.assertAlmostEqual(math.degrees(math.acos(ponto(n, KERBIN.polo))), pedida, delta=0.01)
                self.assertAlmostEqual(usada, pedida, delta=0.01)

    def test_inclinacao_menor_que_a_latitude_sai_na_menor_possivel(self):
        l = NaveSimulada.kerbin(latitude=28.5, longitude=0.0).leitura()
        for pedida in (0.0, 10.0):
            with self.subTest(inclinacao=pedida):
                _, usada = plano_do_lancamento(l, KERBIN, pedida)
                self.assertAlmostEqual(usada, 28.5, delta=0.01)
        _, usada = plano_do_lancamento(l, KERBIN, 28.5)
        self.assertAlmostEqual(usada, 28.5, delta=0.01)

    def test_plano_pela_posicao_no_chao_e_o_do_lancamento(self):
        for latitude in (-0.0972, 0.0, 28.5, 60.0):
            for pedida in (0.0, 45.0, 90.0, 150.0):
                with self.subTest(latitude=latitude, inclinacao=pedida):
                    l = NaveSimulada.kerbin(latitude=latitude, longitude=10.0).leitura()
                    n1, u1 = plano_do_lancamento(l, KERBIN, pedida)
                    n2, u2 = plano_pela_posicao(l, KERBIN, pedida)
                    self.assertLess(angulo(n1, n2), 1e-6)
                    self.assertAlmostEqual(u1, u2)

    def test_plano_pela_posicao_escolhe_o_ramo_pela_velocidade(self):
        l = NaveSimulada.kerbin(latitude=20.0, longitude=0.0).leitura()
        cima = unit(l.r)
        norte = plano_pela_posicao(l, KERBIN, 45.0)[0]
        para_o_norte = dataclasses.replace(l, v=soma(l.v, esc(300.0, l.norte)))
        para_o_sul = dataclasses.replace(l, v=soma(l.v, esc(-300.0, l.norte)))
        n_n, u_n = plano_pela_posicao(para_o_norte, KERBIN, 45.0)
        n_s, u_s = plano_pela_posicao(para_o_sul, KERBIN, 45.0)
        self.assertLess(angulo(n_n, norte), 1e-6)
        self.assertGreater(angulo(n_n, n_s), 1.0)
        self.assertAlmostEqual(u_n, 45.0, delta=0.01)
        self.assertAlmostEqual(u_s, 45.0, delta=0.01)
        d_n = subida.direcao_no_plano(n_n, l.r)
        d_s = subida.direcao_no_plano(n_s, l.r)
        self.assertGreater(ponto(d_n, l.norte), 0.0)
        self.assertLess(ponto(d_s, l.norte), 0.0)
        self.assertAlmostEqual(ponto(d_n, cima), 0.0, places=6)

    def test_plano_pela_posicao_acompanha_a_latitude(self):
        l = NaveSimulada.kerbin(latitude=0.0, longitude=0.0).leitura()
        longe = NaveSimulada.kerbin(latitude=30.0, longitude=0.0).leitura()
        longe = dataclasses.replace(longe, v=soma(longe.v, esc(500.0, longe.norte)))
        for leitura in (l, longe):
            n, usada = plano_pela_posicao(leitura, KERBIN, 45.0)
            self.assertAlmostEqual(usada, 45.0, delta=0.01)
            self.assertAlmostEqual(ponto(n, unit(leitura.r)), 0.0, places=6)

    def test_rumo_do_plano_no_chao_do_equador(self):
        l = NaveSimulada.kerbin(latitude=0.0, longitude=0.0).leitura()
        alvo_raio = KERBIN.raio + 80_000.0
        n45, _ = plano_do_lancamento(l, KERBIN, 45.0)
        self.assertAlmostEqual(rumo_do_plano(l, KERBIN, n45, alvo_raio), 41.7, delta=0.3)
        n0, _ = plano_do_lancamento(l, KERBIN, 0.0)
        self.assertAlmostEqual(rumo_do_plano(l, KERBIN, n0, alvo_raio), 90.0, delta=0.01)
        n180, _ = plano_do_lancamento(l, KERBIN, 180.0)
        self.assertAlmostEqual(rumo_do_plano(l, KERBIN, n180, alvo_raio), 270.0, delta=0.01)

    def test_janela_para_um_plano_montado_para_um_instante_conhecido(self):
        nave = NaveSimulada.kerbin(latitude=0.0, longitude=0.0)
        l = nave.leitura()
        for atraso in (3_000.0, 7_200.0):
            for sentido in (1, -1):
                with self.subTest(atraso=atraso, sentido=sentido):
                    n_alvo = plano_com_janela(nave, atraso, 30.0, sentido)
                    janela = proxima_janela(l, KERBIN, n_alvo)
                    self.assertAlmostEqual(janela, l.t + atraso, delta=1.0)

    def test_janela_escolhe_a_primeira_das_duas_do_dia(self):
        nave = NaveSimulada.kerbin(latitude=0.0, longitude=0.0)
        l = nave.leitura()
        n_alvo = plano_com_janela(nave, 15_000.0, 30.0)
        janela = proxima_janela(l, KERBIN, n_alvo)
        self.assertAlmostEqual(janela, 15_000.0 - KERBIN.periodo / 2, delta=40.0)

    def test_janela_nao_existe_se_a_latitude_passa_da_inclinacao_do_alvo(self):
        l = NaveSimulada.kerbin(latitude=10.0, longitude=0.0).leitura()
        self.assertIsNone(proxima_janela(l, KERBIN, KERBIN.polo))
        cinco = math.radians(5.0)
        self.assertIsNone(proxima_janela(l, KERBIN, unit((math.sin(cinco), math.cos(cinco), 0.0))))


class TestGiro(unittest.TestCase):
    def setUp(self):
        self.estagios = NaveSimulada.kerbin().estagios()
        self.estado = EstadoSim(KERBIN.raio + 223.0, 50.0, 175.0)

    def custo(self, giro, area=1.0):
        return simular(KERBIN, self.estagios, self.estado, giro, 80_000.0, area, 175.0)[0]

    def test_giro_escolhido_fica_na_faixa_e_custa_menos_que_os_extremos(self):
        giro, achou = escolher_giro(KERBIN, self.estagios, self.estado, 80_000.0, 1.0, 175.0)
        baixo, alto = subida.GIRO_AR
        self.assertTrue(achou)
        self.assertGreaterEqual(giro, baixo)
        self.assertLessEqual(giro, alto)
        escolhido = self.custo(giro)
        self.assertTrue(math.isfinite(escolhido))
        self.assertLessEqual(escolhido, self.custo(baixo))
        self.assertLessEqual(escolhido, self.custo(alto))
        self.assertLess(escolhido, self.custo(baixo) - 100.0)

    def test_giro_escolhido_custa_menos_que_os_vizinhos(self):
        giro, _ = escolher_giro(KERBIN, self.estagios, self.estado, 80_000.0, 1.0, 175.0)
        for desvio in (-1.0, 1.0):
            with self.subTest(desvio=desvio):
                self.assertLessEqual(self.custo(giro), self.custo(giro + desvio) + 1e-6)

    def test_giro_grande_demais_e_inviavel(self):
        self.assertTrue(math.isinf(self.custo(30.0)))

    def test_sem_arrasto_o_dv_e_menor(self):
        self.assertLess(self.custo(6.0, area=0.0), self.custo(6.0, area=1.0))

    def test_simulacao_devolve_dv_e_duracao_plausiveis(self):
        dv, duracao = simular(KERBIN, self.estagios, self.estado, 6.0, 80_000.0, 1.0, 175.0)
        self.assertTrue(3_000.0 < dv < 3_500.0)
        self.assertTrue(100.0 < duracao < 400.0)

    def test_sem_combustivel_devolve_o_giro_padrao(self):
        pouco = [dataclasses.replace(self.estagios[0], combustivel=1_000.0), self.estagios[1]]
        giro, achou = escolher_giro(KERBIN, pouco, self.estado, 80_000.0, 1.0, 175.0)
        self.assertFalse(achou)
        self.assertEqual(giro, subida.GIRO_PADRAO_AR)

    def test_sem_ar_a_faixa_e_a_do_vacuo(self):
        estagios = NaveSimulada.mun().estagios()
        estado = EstadoSim(MUN.raio + 300.0, 50.0, 9.0)
        giro, achou = escolher_giro(MUN, estagios, estado, 20_000.0, 0.0, 9.0)
        baixo, alto = subida.GIRO_VACUO
        self.assertTrue(achou)
        self.assertTrue(baixo <= giro <= alto)
        self.assertLessEqual(simular(MUN, estagios, estado, giro, 20_000.0, 0.0, 9.0)[0],
                             simular(MUN, estagios, estado, baixo, 20_000.0, 0.0, 9.0)[0])


class TestNaveSimulada(unittest.TestCase):
    def test_parada_no_chao_gira_com_o_planeta(self):
        nave = NaveSimulada.kerbin(latitude=10.0, longitude=20.0)
        r0 = nave.r
        l = nave.leitura()
        self.assertTrue(l.pousada)
        self.assertAlmostEqual(l.radar, 0.0, places=6)
        self.assertLess(subida.norma(l.v_sup), 1e-6)
        nave.avancar(100.0)
        esperado = rotacionar(r0, KERBIN.polo, KERBIN.omega * 100.0)
        self.assertLess(subida.norma(subida.sub(nave.r, esperado)), 1e-3)
        self.assertAlmostEqual(nave.t, 100.0)
        self.assertTrue(nave.leitura().pousada)

    def test_leste_e_para_onde_o_planeta_gira(self):
        l = NaveSimulada.kerbin(latitude=15.0, longitude=40.0).leitura()
        self.assertGreater(ponto(l.v, l.leste), 0.0)
        self.assertAlmostEqual(ponto(l.leste, l.norte), 0.0, places=9)
        self.assertLess(angulo(cruz(l.leste, l.norte), unit(l.r)), 1e-6)

    def test_sem_a_ignicao_o_motor_nao_acende(self):
        nave = NaveSimulada.kerbin()
        l = nave.leitura()
        self.assertEqual(l.empuxo, 0.0)
        self.assertTrue(l.motor_abaixo)
        self.assertFalse(l.apagado)
        nave.executar(Comando(acelerador=1.0))
        nave.avancar(5.0)
        self.assertTrue(nave.leitura().pousada)

    def test_depois_da_ignicao_sobe_e_gasta_combustivel(self):
        nave = NaveSimulada.kerbin()
        nave.executar(Comando(acelerador=1.0, estagiar=True))
        l = nave.leitura()
        self.assertEqual(l.empuxo, 300_000.0)
        self.assertEqual(l.isp, 280.0)
        massa0 = l.massa
        nave.avancar(1.0)
        l = nave.leitura()
        self.assertFalse(l.pousada)
        self.assertGreater(l.radar, 0.5)
        self.assertAlmostEqual(massa0 - l.massa, 300_000.0 / (280.0 * subida.G0), delta=0.5)

    def test_empuxo_fraco_nao_tira_a_nave_do_chao(self):
        nave = NaveSimulada.kerbin(aceso=True)
        nave.executar(Comando(acelerador=0.4))
        nave.avancar(10.0)
        self.assertTrue(nave.leitura().pousada)
        self.assertAlmostEqual(nave.leitura().radar, 0.0, places=6)

    def test_estagiar_larga_o_estagio_de_baixo(self):
        nave = NaveSimulada.kerbin(aceso=True)
        antes = nave.massa
        nave.executar(Comando(estagiar=True))
        self.assertEqual(nave.indice, 1)
        self.assertAlmostEqual(antes - nave.massa, 2_000.0 + 13_000.0)
        l = nave.leitura()
        self.assertFalse(l.motor_abaixo)
        self.assertEqual(l.isp, subida.FOGUETE_KERBIN[1].isp_mar)
        massa = nave.massa
        nave.executar(Comando(estagiar=True))
        self.assertEqual(nave.indice, 1)
        self.assertEqual(nave.massa, massa)

    def test_estagio_sem_combustivel_fica_apagado(self):
        nave = NaveSimulada.kerbin(aceso=True)
        nave.combustivel = 0.0
        l = nave.leitura()
        self.assertTrue(l.apagado)
        self.assertEqual(l.empuxo, 0.0)
        self.assertTrue(l.motor_abaixo)

    def test_estagios_a_partir_do_de_agora(self):
        nave = NaveSimulada.kerbin(aceso=True)
        nave.executar(Comando(acelerador=1.0))
        nave.avancar(3.0)
        estagios = nave.estagios()
        self.assertEqual(len(estagios), 2)
        self.assertAlmostEqual(estagios[0].massa_inicial, nave.massa)
        self.assertAlmostEqual(estagios[0].combustivel, nave.combustivel)
        esperado = estagios[0].massa_inicial - estagios[0].combustivel - estagios[0].seca_solta
        self.assertAlmostEqual(estagios[1].massa_inicial, esperado)
        nave.executar(Comando(estagiar=True))
        self.assertEqual(len(nave.estagios()), 1)

    def test_nariz_gira_no_maximo_15_graus_por_segundo(self):
        nave = NaveSimulada.kerbin()
        nave.executar(Comando(pitch=0.0, rumo=90.0))
        nave.avancar(1.0)
        l = nave.leitura()
        self.assertAlmostEqual(angulo(l.nariz, unit(l.r)), subida.GIRO_NARIZ_MAX, delta=0.5)
        nave.avancar(10.0)
        l = nave.leitura()
        self.assertAlmostEqual(angulo(l.nariz, unit(l.r)), 90.0, delta=0.5)
        self.assertGreater(ponto(l.nariz, l.leste), 0.99)

    def test_time_warp_no_chao_e_no_espaco(self):
        nave = NaveSimulada.kerbin(latitude=5.0, longitude=0.0)
        nave.executar(Comando(acelerar_ate=5_000.0))
        self.assertAlmostEqual(nave.t, 5_000.0)
        self.assertTrue(nave.leitura().pousada)
        self.assertAlmostEqual(subida.norma(nave.r), KERBIN.raio, delta=1e-3)

        r = KERBIN.raio + 80_000.0
        v = math.sqrt(KERBIN.mu / r) * 1.05
        nave = NaveSimulada.kerbin()
        nave.pousada = False
        nave.r, nave.v = (r, 0.0, 0.0), (0.0, 0.0, -v)
        antes = elementos(KERBIN, nave.r, nave.v)
        nave.executar(Comando(acelerar_ate=10_000.0))
        depois = elementos(KERBIN, nave.r, nave.v)
        self.assertAlmostEqual(nave.t, 10_000.0)
        self.assertAlmostEqual(depois[2], antes[2], delta=20.0)
        self.assertAlmostEqual(depois[3], antes[3], delta=20.0)


class TestGuiagem(unittest.TestCase):
    def test_fase_janela_espera_sem_motor_e_pede_warp(self):
        nave = NaveSimulada.kerbin()
        n_alvo = plano_com_janela(nave, 7_200.0, 30.0)
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, n_alvo=n_alvo)
        comando = guiagem.passo(nave.leitura())
        self.assertEqual(guiagem.fase, JANELA)
        self.assertEqual(comando.acelerador, 0.0)
        self.assertFalse(comando.estagiar)
        self.assertAlmostEqual(guiagem.janela, 7_200.0, delta=1.0)
        self.assertAlmostEqual(comando.acelerar_ate, guiagem.janela - subida.ESPERA_TEMPO_REAL)
        self.assertAlmostEqual(guiagem.inclinacao_alvo, 30.0, delta=0.01)

    def test_alvo_que_a_base_nunca_alcanca_falha_sem_decolar(self):
        nave = NaveSimulada.kerbin(latitude=10.0, longitude=0.0)
        cinco = math.radians(5.0)
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, n_alvo=unit((math.sin(cinco), math.cos(cinco), 0.0)),
                          ler_estagios=nave.estagios)
        resultado = voar(nave, guiagem)
        self.assertEqual(resultado.fase, FALHA)
        self.assertEqual(guiagem.aviso, subida.AVISO_INCLINACAO)
        self.assertIsNone(guiagem.janela)
        self.assertEqual(resultado.comandos_de_estagio, 0)
        self.assertTrue(nave.leitura().pousada)

    def test_aviso_mais_importante_vem_primeiro(self):
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0)
        self.assertIsNone(guiagem.aviso)
        guiagem._avisar(subida.AVISO_EMPUXO)
        self.assertEqual(guiagem.aviso, subida.AVISO_EMPUXO)
        guiagem._avisar(subida.AVISO_INCLINACAO)
        self.assertEqual(guiagem.aviso, subida.AVISO_INCLINACAO)
        guiagem._avisar(subida.AVISO_COMBUSTIVEL)
        self.assertEqual(guiagem.aviso, subida.AVISO_COMBUSTIVEL)

    def test_ignicao_no_primeiro_passo(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, ler_estagios=nave.estagios)
        comando = guiagem.passo(nave.leitura())
        self.assertEqual(guiagem.fase, DECOLAGEM)
        self.assertTrue(comando.estagiar)
        self.assertEqual(comando.acelerador, 1.0)
        self.assertEqual(comando.pitch, 90.0)
        nave.executar(comando)
        nave.avancar(DT)
        comando = guiagem.passo(nave.leitura())
        self.assertFalse(comando.estagiar)

    def test_area_de_arrasto_medida_em_voo(self):
        resultado = subir_de_kerbin(80_000.0, 0.0)
        self.assertAlmostEqual(resultado.guiagem.area, subida.AREA_FOGUETE_KERBIN, delta=0.05)

    def test_plano_sem_alvo_e_refeito_pela_posicao(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 100_000.0, 45.0, ler_estagios=nave.estagios)
        guiagem.passo(nave.leitura())
        primeiro = guiagem.n
        self.assertAlmostEqual(guiagem.inclinacao_alvo, 45.0, delta=0.01)
        for _ in range(600):
            comando = guiagem.passo(nave.leitura())
            nave.executar(comando)
            nave.avancar(DT)
        self.assertGreater(angulo(guiagem.n, primeiro), 0.1)
        self.assertAlmostEqual(guiagem.inclinacao_alvo, 45.0, delta=0.01)


class TestVoos(unittest.TestCase):
    def test_kerbin_80_km_no_equador(self):
        r = subir_de_kerbin(80_000.0, 0.0)
        self.assertEqual(r.fase, ORBITA)
        self.assertEqual(r.fases[0], DECOLAGEM)
        self.assertEqual(r.fases[-1], ORBITA)
        for fase in (subida.GIRO, subida.CURVA, COSTA, subida.CIRCULARIZA):
            self.assertIn(fase, r.fases)
        self.assertNotIn(JANELA, r.fases)
        self.assertNotIn(PLANO, r.fases)
        self.assertTrue(78_500.0 < r.ap < 81_500.0, r.ap)
        self.assertTrue(78_500.0 < r.pe < 81_500.0, r.pe)
        self.assertLess(r.inclinacao, 0.5)
        self.assertTrue(3_000.0 < r.dv < 4_200.0, r.dv)
        self.assertEqual(r.nave.indice, 1)
        self.assertEqual(r.comandos_de_estagio, 2)
        self.assertIsNone(r.guiagem.aviso)
        self.assertEqual(r.guiagem.acelerador, 0.0)

    def test_foguete_que_so_vira_com_empuxo(self):
        nave = NaveSimulada.kerbin()
        nave.giro_sem_empuxo = 0.0
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, ler_estagios=nave.estagios)
        r = voar(nave, guiagem)
        self.assertEqual(r.fase, ORBITA)
        self.assertTrue(78_500.0 < r.ap < 81_500.0, r.ap)
        self.assertTrue(78_500.0 < r.pe < 81_500.0, r.pe)
        self.assertTrue(3_000.0 < r.dv < 4_200.0, r.dv)

    def test_desalinhado_o_motor_fica_baixo_para_virar(self):
        nave = NaveSimulada.kerbin(aceso=True)
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, ler_estagios=nave.estagios)
        l = nave.leitura()
        guiagem._w_min = math.inf
        w = esc(500.0, l.leste)
        self.assertEqual(guiagem._queimar(l, w).acelerador, subida.ACEL_VIRAR)
        self.assertLess(guiagem._queimar(l, esc(0.5, l.leste)).acelerador, subida.ACEL_VIRAR)

    def test_acelerador_de_virada_pelo_logaritmo_do_erro(self):
        virada = subida.acelerador_de_virada
        self.assertEqual(virada(0.0), 1.0)
        self.assertEqual(virada(subida.ERRO_APONTAR), 1.0)
        self.assertEqual(virada(subida.ERRO_VIRAR), subida.ACEL_VIRAR)
        self.assertEqual(virada(120.0), subida.ACEL_VIRAR)
        meio = math.sqrt(subida.ERRO_APONTAR * subida.ERRO_VIRAR)
        self.assertAlmostEqual(virada(meio), (1.0 + subida.ACEL_VIRAR) / 2.0)
        valores = [virada(e) for e in range(5, 46)]
        self.assertTrue(all(a > b for a, b in zip(valores, valores[1:])))

    def test_kerbin_100_km_a_45_graus(self):
        r = subir_de_kerbin(100_000.0, 45.0)
        self.assertEqual(r.fase, ORBITA)
        self.assertAlmostEqual(r.inclinacao, 45.0, delta=0.5)
        self.assertTrue(98_500.0 < r.ap < 101_500.0, r.ap)
        self.assertTrue(98_500.0 < r.pe < 101_500.0, r.pe)

    def test_inclinacoes_variadas_e_latitudes_variadas(self):
        casos = [
            (28.5, subida.LATITUDE_KSC),
            (60.0, subida.LATITUDE_KSC),
            (90.0, subida.LATITUDE_KSC),
            (120.0, subida.LATITUDE_KSC),
            (180.0, subida.LATITUDE_KSC),
            (45.0, 28.5),
            (60.0, 28.5),
            (90.0, 28.5),
            (150.0, 28.5),
            (45.0, -30.0),
            (98.0, 60.0),
        ]
        for pedida, latitude in casos:
            with self.subTest(inclinacao=pedida, latitude=latitude):
                r = subir_de_kerbin(80_000.0, pedida, latitude=latitude)
                self.assertEqual(r.fase, ORBITA)
                self.assertAlmostEqual(r.inclinacao, pedida, delta=0.5)
                self.assertTrue(78_500.0 < r.pe < r.ap < 81_500.0, (r.pe, r.ap))
                self.assertIsNone(r.guiagem.aviso)

    def test_inclinacao_menor_que_a_latitude_sai_na_possivel_com_aviso(self):
        for pedida, latitude in ((10.0, 28.5), (0.0, 28.5), (20.0, 45.0)):
            with self.subTest(inclinacao=pedida, latitude=latitude):
                r = subir_de_kerbin(80_000.0, pedida, latitude=latitude)
                self.assertEqual(r.fase, ORBITA)
                self.assertAlmostEqual(r.inclinacao, latitude, delta=0.5)
                self.assertEqual(r.guiagem.aviso, subida.AVISO_INCLINACAO)
                self.assertAlmostEqual(r.guiagem.inclinacao_alvo, latitude, delta=0.01)

    def test_outras_altitudes(self):
        for altitude in (75_000.0, 200_000.0, 700_000.0):
            with self.subTest(altitude=altitude):
                r = subir_de_kerbin(altitude, 0.0)
                self.assertEqual(r.fase, ORBITA)
                self.assertAlmostEqual(r.ap, altitude, delta=1_000.0)
                self.assertAlmostEqual(r.pe, altitude, delta=1_000.0)

    def test_plano_de_um_alvo_com_a_janela_umas_horas_a_frente(self):
        for atraso, sentido in ((7_200.0, 1), (7_200.0, -1), (5_000.0, 1)):
            with self.subTest(atraso=atraso, sentido=sentido):
                nave = NaveSimulada.kerbin()
                n_alvo = plano_com_janela(nave, atraso, 30.0, sentido)
                guiagem = Guiagem(KERBIN, 80_000.0, 0.0, n_alvo=n_alvo, ler_estagios=nave.estagios)
                r = voar(nave, guiagem)
                self.assertEqual(r.fase, ORBITA)
                self.assertEqual(r.fases[0], JANELA)
                self.assertEqual(r.fases[1], DECOLAGEM)
                self.assertIn(PLANO, r.fases)
                self.assertAlmostEqual(guiagem.janela, atraso, delta=1.0)
                self.assertLess(r.erro_de_plano(n_alvo), 0.1)
                self.assertAlmostEqual(r.inclinacao, 30.0, delta=0.1)
                self.assertTrue(78_500.0 < r.pe < r.ap < 81_500.0, (r.pe, r.ap))
                self.assertTrue(3_000.0 < r.dv < 4_500.0, r.dv)

    def test_decolagem_so_depois_da_janela(self):
        nave = NaveSimulada.kerbin()
        n_alvo = plano_com_janela(nave, 7_200.0, 30.0)
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, n_alvo=n_alvo, ler_estagios=nave.estagios)
        for _ in range(PASSOS_MAX):
            l = nave.leitura()
            comando = guiagem.passo(l)
            if guiagem.fase != JANELA:
                break
            nave.executar(comando)
            nave.avancar(DT)
        self.assertGreaterEqual(l.t, guiagem.janela - 1e-6)
        self.assertLess(l.t, guiagem.janela + 1.0)
        self.assertTrue(l.pousada)

    def test_mun_20_km(self):
        nave = NaveSimulada.mun()
        guiagem = Guiagem(MUN, 20_000.0, 0.0, ler_estagios=nave.estagios)
        r = voar(nave, guiagem)
        self.assertEqual(r.fase, ORBITA)
        self.assertTrue(19_000.0 < r.pe < r.ap < 21_000.0, (r.pe, r.ap))
        self.assertLess(r.inclinacao, 0.5)
        self.assertEqual(r.comandos_de_estagio, 1)
        self.assertNotIn(subida.CURVA, r.fases)

    def test_mun_com_inclinacao(self):
        nave = NaveSimulada.mun()
        guiagem = Guiagem(MUN, 50_000.0, 30.0, ler_estagios=nave.estagios)
        r = voar(nave, guiagem)
        self.assertEqual(r.fase, ORBITA)
        self.assertAlmostEqual(r.inclinacao, 30.0, delta=0.5)
        self.assertTrue(48_000.0 < r.pe < r.ap < 52_000.0, (r.pe, r.ap))

    def test_estagio_de_cima_sem_combustivel_suficiente_falha(self):
        r = subir_de_kerbin(80_000.0, 0.0, estagios=estagios_kerbin(5_500.0, 300.0))
        self.assertEqual(r.fase, FALHA)
        self.assertEqual(r.guiagem.aviso, subida.AVISO_COMBUSTIVEL)
        self.assertEqual(r.guiagem.acelerador, 0.0)
        self.assertLess(r.pe, KERBIN.topo)
        self.assertLessEqual(r.comandos_de_estagio, 2)

    def test_foguete_com_quase_nada_de_combustivel_falha(self):
        r = subir_de_kerbin(80_000.0, 0.0, estagios=estagios_kerbin(1_000.0, 100.0))
        self.assertEqual(r.fase, FALHA)
        self.assertEqual(r.guiagem.aviso, subida.AVISO_COMBUSTIVEL)

    def test_motor_ja_aceso_so_troca_de_estagio_uma_vez(self):
        r = subir_de_kerbin(80_000.0, 0.0, aceso=True)
        self.assertEqual(r.fase, ORBITA)
        self.assertEqual(r.comandos_de_estagio, 1)

    def test_sem_ler_estagios_usa_o_giro_padrao_e_chega_em_orbita(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0)
        r = voar(nave, guiagem)
        self.assertEqual(r.fase, ORBITA)
        self.assertEqual(guiagem.giro, subida.GIRO_PADRAO_AR)
        self.assertTrue(77_000.0 < r.pe < r.ap < 82_000.0, (r.pe, r.ap))


FASES_SUB = {
    "JANELA", "DECOLAGEM", "GIRO", "CURVA", "VACUO", "COSTA", "CIRCULARIZA", "PLANO", "ORBITA", "FALHA",
}
AVISOS_SUB = {"EMPUXO", "ALTITUDE", "INCLINACAO", "ALVO", "COMBUSTIVEL"}
ORDEM_SUB = ["FASE", "ALT", "VEL", "AP", "PE", "ALVO", "Q", "INC", "INCA", "DV", "JAN", "GIRO", "MOTOR", "AVISO"]


def _inteiro(texto):
    return re.fullmatch(r"-?\d+", texto) is not None


def _inteiro_ou_off(texto):
    return texto == "OFF" or _inteiro(texto)


VALIDADORES_SUB = {
    "FASE": lambda v: v in FASES_SUB,
    "ALT": _inteiro,
    "VEL": _inteiro,
    "AP": _inteiro_ou_off,
    "PE": _inteiro_ou_off,
    "ALVO": _inteiro,
    "Q": _inteiro,
    "INC": _inteiro,
    "INCA": _inteiro,
    "DV": _inteiro,
    "JAN": _inteiro_ou_off,
    "GIRO": _inteiro_ou_off,
    "MOTOR": lambda v: _inteiro(v) and 0 <= int(v) <= 100,
    "AVISO": lambda v: v == "OFF" or v in AVISOS_SUB,
}


def valores_sub(linhas):
    return {linha.split(" ", 2)[1]: linha.split(" ", 2)[2] for linha in linhas}


def voar_coletando(nave, guiagem, a_cada=50):
    """Como voar(), mas guarda as linhas SUB a cada `a_cada` passos e a cada troca de fase."""
    coletadas = []
    fase = None
    for passo in range(PASSOS_MAX):
        l = nave.leitura()
        comando = guiagem.passo(l)
        if guiagem.fase != fase or passo % a_cada == 0:
            fase = guiagem.fase
            coletadas.append(subida.linhas_de_estado(l, guiagem, nave.corpo))
        if guiagem.fase in (ORBITA, FALHA) or nave.t > T_MAX_JOGO:
            coletadas.append(subida.linhas_de_estado(l, guiagem, nave.corpo))
            break
        nave.executar(comando)
        nave.avancar(DT)
    return coletadas


class TestLinhasDeEstado(unittest.TestCase):
    def conferir(self, linhas):
        self.assertEqual([linha.split(" ")[1] for linha in linhas], ORDEM_SUB)
        for linha in linhas:
            with self.subTest(linha=linha):
                self.assertLessEqual(len(linha), 31)
                self.assertTrue(linha.isascii())
                partes = linha.split(" ", 2)
                self.assertEqual(len(partes), 3)
                self.assertEqual(partes[0], "SUB")
                self.assertTrue(VALIDADORES_SUB[partes[1]](partes[2]), linha)

    def test_voo_com_janela_e_troca_de_plano(self):
        nave = NaveSimulada.kerbin()
        n_alvo = plano_com_janela(nave, 7_200.0, 30.0)
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, n_alvo=n_alvo, ler_estagios=nave.estagios)
        coletadas = voar_coletando(nave, guiagem)
        fases = []
        for linhas in coletadas:
            self.conferir(linhas)
            valores = valores_sub(linhas)
            if not fases or fases[-1] != valores["FASE"]:
                fases.append(valores["FASE"])
            self.assertEqual(valores["ALVO"], "80000")
            self.assertEqual(valores["INCA"], "300")
            self.assertEqual(valores["JAN"] != "OFF", valores["FASE"] == "JANELA")
            self.assertEqual(valores["GIRO"] != "OFF", valores["FASE"] not in ("JANELA", "DECOLAGEM"))
        for fase in ("JANELA", "DECOLAGEM", "GIRO", "CURVA", "COSTA", "CIRCULARIZA", "PLANO", "ORBITA"):
            self.assertIn(fase, fases)
        primeira = valores_sub(coletadas[0])
        self.assertEqual(primeira["FASE"], "JANELA")
        self.assertTrue(7_190 <= int(primeira["JAN"]) <= 7_210)
        self.assertEqual(primeira["MOTOR"], "0")
        ultima = valores_sub(coletadas[-1])
        self.assertEqual(ultima["FASE"], "ORBITA")
        self.assertEqual(ultima["MOTOR"], "0")
        self.assertEqual(ultima["AVISO"], "OFF")
        self.assertTrue(abs(int(ultima["INC"]) - 300) <= 1)
        self.assertTrue(78_500 < int(ultima["PE"]) < int(ultima["AP"]) < 81_500)
        self.assertTrue(3_000 < int(ultima["DV"]) < 4_500)

    def test_valores_da_subida_sem_alvo(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 100_000.0, 45.0, ler_estagios=nave.estagios)
        coletadas = voar_coletando(nave, guiagem)
        for linhas in coletadas:
            self.conferir(linhas)
        inicio = valores_sub(coletadas[0])
        self.assertEqual(inicio["JAN"], "OFF")
        self.assertEqual(inicio["GIRO"], "OFF")
        self.assertEqual(inicio["INCA"], "450")
        self.assertEqual(inicio["ALT"], "0")
        meio = [valores_sub(linhas) for linhas in coletadas if valores_sub(linhas)["FASE"] == "CURVA"]
        self.assertTrue(meio)
        self.assertTrue(all(int(v["Q"]) >= 0 for v in meio))
        self.assertTrue(any(int(v["Q"]) > 1_000 for v in meio))

    def test_avisos_na_linha(self):
        r = subir_de_kerbin(80_000.0, 10.0, latitude=28.5)
        l = r.nave.leitura()
        linhas = subida.linhas_de_estado(l, r.guiagem, KERBIN)
        self.conferir(linhas)
        self.assertEqual(valores_sub(linhas)["AVISO"], "INCLINACAO")

        r = subir_de_kerbin(80_000.0, 0.0, estagios=estagios_kerbin(5_500.0, 300.0))
        linhas = subida.linhas_de_estado(r.nave.leitura(), r.guiagem, KERBIN)
        self.conferir(linhas)
        valores = valores_sub(linhas)
        self.assertEqual(valores["AVISO"], "COMBUSTIVEL")
        self.assertEqual(valores["FASE"], "FALHA")
        self.assertEqual(valores["MOTOR"], "0")

    def test_recusa_sai_com_falha_e_aviso(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 50_000.0, 0.0)
        guiagem.recusar(subida.AVISO_ALTITUDE)
        linhas = subida.linhas_de_estado(nave.leitura(), guiagem, KERBIN)
        self.conferir(linhas)
        valores = valores_sub(linhas)
        self.assertEqual(valores["FASE"], "FALHA")
        self.assertEqual(valores["AVISO"], "ALTITUDE")
        self.assertEqual(guiagem.passo(nave.leitura()).acelerador, 0.0)
        self.assertEqual(guiagem.fase, FALHA)

    def test_escape_nao_tem_apoastro(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0)
        l = nave.leitura()
        r = KERBIN.raio + 100_000.0
        rapido = dataclasses.replace(l, r=(r, 0.0, 0.0), v=(0.0, 0.0, -1.5 * math.sqrt(2.0 * KERBIN.mu / r)))
        linhas = subida.linhas_de_estado(rapido, guiagem, KERBIN)
        self.conferir(linhas)
        self.assertEqual(valores_sub(linhas)["AP"], "OFF")
        self.assertTrue(_inteiro(valores_sub(linhas)["PE"]))

    def test_inteiros_ficam_dentro_dos_32_bits(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0)
        guiagem.dv = 1e15
        l = nave.leitura()
        longe = dataclasses.replace(l, r=(1e15, 0.0, 0.0), q=1e15)
        linhas = subida.linhas_de_estado(longe, guiagem, KERBIN)
        self.conferir(linhas)
        valores = valores_sub(linhas)
        for campo in ("ALT", "DV", "Q"):
            self.assertEqual(valores[campo], str(2**31 - 1))

    def test_periastro_dentro_do_planeta_e_negativo(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0)
        linhas = subida.linhas_de_estado(nave.leitura(), guiagem, KERBIN)
        self.conferir(linhas)
        self.assertLess(int(valores_sub(linhas)["PE"]), 0)


NR = "nr"
SUP = "sup"
CORPO_GIRATORIO = "corpo"
HIBRIDO = "hibrido"


class FluxoFalso:
    def __init__(self, funcao, argumentos):
        self.funcao = funcao
        self.argumentos = argumentos
        self.removido = False

    def __call__(self):
        return self.funcao(*self.argumentos)

    def remove(self):
        self.removido = True


class PecaFalsa:
    def __init__(self, stage, decouple_stage, dry_mass, combustivel=None):
        self.stage = stage
        self.decouple_stage = decouple_stage
        self.dry_mass = dry_mass
        self._combustivel = combustivel

    @property
    def mass(self):
        return self.dry_mass + (self._combustivel() if self._combustivel else 0.0)


class MotorFalso:
    def __init__(self, jogo, indice, peca):
        self.jogo = jogo
        self.indice = indice
        self.part = peca

    @property
    def active(self):
        sim = self.jogo.sim
        return sim.aceso and sim.indice == self.indice

    @property
    def has_fuel(self):
        sim = self.jogo.sim
        return sim.combustivel > 0.0 if sim.indice == self.indice else True

    def max_thrust_at(self, pressao):
        return subida.empuxo_em(subida.FOGUETE_KERBIN[self.indice], pressao)

    def specific_impulse_at(self, pressao):
        return subida.isp_em(subida.FOGUETE_KERBIN[self.indice], pressao)


class PartesFalsas:
    def __init__(self, jogo):
        sim = jogo.sim
        cima = sim._estagios[-1].combustivel
        self.jogo = jogo
        self.tanque_baixo = PecaFalsa(-1, 0, 1_500.0, lambda: sim.combustivel if sim.indice == 0 else 0.0)
        self.peca_motor_baixo = PecaFalsa(1, 0, 500.0)
        self.tanque_cima = PecaFalsa(-1, -1, 400.0, lambda: sim.combustivel if sim.indice == 1 else cima)
        self.peca_motor_cima = PecaFalsa(0, -1, 300.0)
        self.carga = PecaFalsa(-1, -1, 500.0)
        self.motor_baixo = MotorFalso(jogo, 0, self.peca_motor_baixo)
        self.motor_cima = MotorFalso(jogo, 1, self.peca_motor_cima)

    @property
    def engines(self):
        sim = self.jogo.sim
        return [m for m in (self.motor_baixo, self.motor_cima) if m.indice >= sim.indice]

    @property
    def all(self):
        sim = self.jogo.sim
        pecas = [self.tanque_cima, self.peca_motor_cima, self.carga]
        if sim.indice == 0:
            pecas = [self.tanque_baixo, self.peca_motor_baixo] + pecas
        return pecas


class ControleFalso:
    def __init__(self, jogo):
        self.jogo = jogo
        self.sas = True
        self.rcs = False
        self.throttle = 0.0
        self.current_stage = 2

    def activate_next_stage(self):
        self.current_stage -= 1
        self.jogo.sim.executar(Comando(estagiar=True))


class PilotoFalso:
    def __init__(self):
        self.reference_frame = None
        self.engajado = False
        self.quebrado = False
        self.servidor_antigo = False
        self.target_roll = 0.0
        self.pitch = 90.0
        self.heading = 90.0

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

    def target_pitch_and_heading(self, pitch, heading):
        self.pitch, self.heading = pitch, heading


class VooFalso:
    def __init__(self, jogo, referencia):
        self.jogo = jogo
        self.referencia = referencia

    @property
    def velocity(self):
        l = self.jogo.sim.leitura()
        return self.jogo.eixos(l.v_sup if self.referencia == HIBRIDO else l.v)

    @property
    def normal(self):
        l = self.jogo.sim.leitura()
        return self.jogo.eixos(unit(cruz(l.r, l.v)))

    @property
    def surface_altitude(self):
        return self.jogo.sim.leitura().radar

    @property
    def dynamic_pressure(self):
        return self.jogo.sim.leitura().q

    @property
    def static_pressure(self):
        return self.jogo.sim.leitura().pressao * subida.PASCAL_POR_ATM

    @property
    def drag(self):
        return (self.jogo.sim.leitura().arrasto, 0.0, 0.0)


class NaveFalsa:
    name = "Foguete falso"

    def __init__(self, jogo):
        self.jogo = jogo
        self.orbit = types.SimpleNamespace(body=jogo.corpo)
        self.surface_reference_frame = SUP
        self.control = ControleFalso(jogo)
        self.auto_pilot = PilotoFalso()
        self.parts = PartesFalsas(jogo)

    def position(self, referencia):
        return self.jogo.eixos(self.jogo.sim.r)

    def velocity(self, referencia):
        return self.jogo.eixos(self.jogo.sim.v)

    def direction(self, referencia):
        return self.jogo.eixos(self.jogo.sim.nariz)

    def flight(self, referencia=None):
        return VooFalso(self.jogo, referencia)

    @property
    def mass(self):
        return self.jogo.sim.massa

    @property
    def available_thrust(self):
        return self.jogo.sim.leitura().empuxo

    @property
    def specific_impulse(self):
        return self.jogo.sim.leitura().isp

    @property
    def situation(self):
        return "pre_launch" if self.jogo.sim.pousada else "flying"


class CorpoFalso:
    def __init__(self, jogo):
        corpo = jogo.sim.corpo
        self._corpo = corpo
        self.name = corpo.nome
        self.gravitational_parameter = corpo.mu
        self.equatorial_radius = corpo.raio
        self.rotational_period = corpo.periodo
        self.has_atmosphere = corpo.topo > 0.0
        self.atmosphere_depth = corpo.topo
        self.non_rotating_reference_frame = NR
        self.reference_frame = CORPO_GIRATORIO

    def density_at(self, altitude):
        return self._corpo.densidade(altitude)

    def pressure_at(self, altitude):
        return self._corpo.pressao(altitude) * subida.PASCAL_POR_ATM


class CentroFalso:
    def __init__(self, jogo):
        self.jogo = jogo
        self.target_vessel = None
        self.target_body = None
        self.warp_proibido = False
        self.warps = []
        self.duracao_warp = 0.0
        self.ut_em_warp = None
        self.intervalos_de_warp = []
        self.ReferenceFrame = types.SimpleNamespace(create_hybrid=self.criar_hibrido)
        self.VesselSituation = types.SimpleNamespace(
            pre_launch="pre_launch", landed="landed", splashed="splashed", flying="flying"
        )

    @property
    def ut(self):
        return self.jogo.sim.t if self.ut_em_warp is None else self.ut_em_warp

    @property
    def active_vessel(self):
        return self.jogo.nave

    def criar_hibrido(self, position, rotation):
        assert position == CORPO_GIRATORIO and rotation == NR
        return HIBRIDO

    def transform_direction(self, direcao, de, para):
        assert de == SUP and para == NR
        l = self.jogo.sim.leitura()
        base = {(1.0, 0.0, 0.0): unit(l.r), (0.0, 1.0, 0.0): l.norte, (0.0, 0.0, 1.0): l.leste}[
            tuple(float(x) for x in direcao)
        ]
        if self.jogo.leste_errado and tuple(direcao) == (0.0, 0.0, 1.0):
            base = esc(-1.0, base)
        return self.jogo.eixos(base)

    def warp_to(self, ut):
        if self.warp_proibido:
            raise RuntimeError("não dá para acelerar o tempo agora")
        self.warps.append(ut)
        inicio = time.monotonic()
        ut_inicial = self.jogo.sim.t
        if self.duracao_warp > 0.0:
            passos = 10
            for i in range(1, passos + 1):
                dormir(self.duracao_warp / passos)
                self.ut_em_warp = ut_inicial + (ut - ut_inicial) * i / passos
        piloto = self.jogo.nave.auto_pilot
        self.jogo.sim.executar(Comando(0.0, piloto.pitch, piloto.heading, acelerar_ate=ut))
        self.ut_em_warp = None
        self.intervalos_de_warp.append((inicio, time.monotonic()))


class JogoFalso:
    """Um KSP de mentira em volta de uma NaveSimulada, com os eixos canhotos do kRPC (z trocado)."""

    def __init__(self, sim=None, canhoto=True, leste_errado=False):
        self.sim = sim or NaveSimulada.kerbin()
        self.canhoto = canhoto
        self.leste_errado = leste_errado
        self.fluxos = []
        self.procedimentos = []
        self._types = types.SimpleNamespace(class_type=lambda servico, classe: (servico, classe))
        self.fechada = False
        self.corpo = CorpoFalso(self)
        self.space_center = CentroFalso(self)
        self.nave = NaveFalsa(self)

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
        piloto = self.nave.auto_pilot
        self.sim.executar(Comando(controle.throttle, piloto.pitch, piloto.heading))
        self.sim.avancar(dt)

    def alvo_com_plano(self, n_alvo, nome="Alvo falso"):
        """Um alvo em órbita circular no plano de normal n_alvo, em volta do mesmo planeta."""
        corpo = self.sim.corpo
        raio_orbita = corpo.raio + 100_000.0
        direcao = unit(cruz(n_alvo, corpo.polo))
        r = esc(raio_orbita, direcao)
        v = esc(math.sqrt(corpo.mu / raio_orbita), cruz(n_alvo, unit(r)))
        eixos = self.eixos
        return types.SimpleNamespace(
            name=nome,
            orbit=types.SimpleNamespace(body=self.corpo),
            position=lambda referencia: eixos(r),
            velocity=lambda referencia: eixos(v),
        )


class TelaFalsa:
    def __init__(self):
        self.pacotes = []

    def enviar(self, linhas, agora=True):
        self.pacotes.append(list(linhas))

    def fechar(self):
        pass


@contextlib.contextmanager
def sem_espera():
    """Tira as esperas de tempo real, para voar o roteiro todo em poucos segundos de teste."""
    with contextlib.ExitStack() as pilha:
        pilha.enter_context(mock.patch.object(subida.time, "sleep"))
        pilha.enter_context(mock.patch.object(subida, "ESPERA_AVISO", 0.05))
        pilha.enter_context(mock.patch.object(subida, "INTERVALO_MOTORES", 0.0))
        saida = pilha.enter_context(contextlib.redirect_stdout(io.StringIO()))
        yield saida


def argumentos(**extras):
    base = dict(altitude=80_000.0, inclinacao=0.0, plano_do_alvo=False)
    base.update(extras)
    return argparse.Namespace(**base)


class TestNaveKrpc(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(subida, "INTERVALO_MOTORES", 0.0)
        patch.start()
        self.addCleanup(patch.stop)

    def criar(self, **extras):
        jogo = JogoFalso(**extras)
        corpo = subida.corpo_do_jogo(jogo.corpo)
        return jogo, subida.NaveKrpc(jogo, jogo.nave, jogo.corpo, corpo)

    def test_corpo_do_jogo_com_ar(self):
        jogo = JogoFalso()
        corpo = subida.corpo_do_jogo(jogo.corpo)
        self.assertEqual(corpo.nome, "Kerbin")
        self.assertEqual(corpo.mu, KERBIN.mu)
        self.assertEqual(corpo.raio, KERBIN.raio)
        self.assertEqual(corpo.periodo, KERBIN.periodo)
        self.assertEqual(corpo.topo, KERBIN.topo)
        self.assertEqual(corpo.polo, (0.0, 1.0, 0.0))
        for altitude in (0.0, 1_000.0, 10_000.0, 35_000.0, 69_000.0):
            with self.subTest(altitude=altitude):
                self.assertAlmostEqual(corpo.densidade(altitude) / KERBIN.densidade(altitude), 1.0, delta=0.005)
                self.assertAlmostEqual(corpo.pressao(altitude) / KERBIN.pressao(altitude), 1.0, delta=0.005)
        self.assertEqual(corpo.densidade(70_000.0), 0.0)
        self.assertEqual(corpo.pressao(200_000.0), 0.0)
        self.assertAlmostEqual(corpo.pressao(0.0), 1.0)

    def test_corpo_do_jogo_sem_ar(self):
        jogo = JogoFalso(NaveSimulada.mun())
        corpo = subida.corpo_do_jogo(jogo.corpo)
        self.assertEqual(corpo.topo, 0.0)
        self.assertEqual(corpo.densidade(0.0), 0.0)
        self.assertEqual(corpo.pressao(1_000.0), 0.0)

    def test_leitura_igual_a_da_nave_simulada_nos_dois_sentidos_do_referencial(self):
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo, fonte = self.criar(canhoto=canhoto)
                jogo.nave.control.activate_next_stage()
                jogo.nave.control.throttle = 1.0
                jogo.avancar(5.0)
                l = fonte.ler()
                esperada = jogo.sim.leitura()
                for campo in ("r", "v", "v_sup", "norte", "leste", "nariz"):
                    self.assertLess(subida.norma(subida.sub(getattr(l, campo), getattr(esperada, campo))), 1e-6, campo)
                for campo in ("t", "radar", "q", "massa", "empuxo", "isp", "pressao", "arrasto"):
                    self.assertAlmostEqual(getattr(l, campo), getattr(esperada, campo), places=6, msg=campo)
                self.assertFalse(l.pousada)
                self.assertEqual(fonte._sinal_z, -1.0 if canhoto else 1.0)

    def test_leste_errado_levanta_erro_claro(self):
        jogo = JogoFalso(leste_errado=True)
        with self.assertRaises(subida.ReferencialErrado) as erro:
            subida.NaveKrpc(jogo, jogo.nave, jogo.corpo, subida.corpo_do_jogo(jogo.corpo))
        self.assertIn("leste", str(erro.exception))
        self.assertIsInstance(erro.exception, RuntimeError)

    def test_nave_sem_velocidade_nao_calibra(self):
        jogo = JogoFalso()
        jogo.sim.v = (0.0, 0.0, 0.0)
        with self.assertRaises(subida.ReferencialErrado):
            subida.NaveKrpc(jogo, jogo.nave, jogo.corpo, subida.corpo_do_jogo(jogo.corpo))

    def test_motores_apagado_e_abaixo(self):
        jogo, fonte = self.criar()
        l = fonte.ler()
        self.assertTrue(l.pousada)
        self.assertTrue(l.motor_abaixo)
        self.assertFalse(l.apagado)
        self.assertEqual(l.empuxo, 0.0)
        jogo.nave.control.activate_next_stage()
        l = fonte.ler()
        self.assertTrue(l.motor_abaixo)
        self.assertFalse(l.apagado)
        self.assertGreater(l.empuxo, 0.0)
        jogo.sim.combustivel = 0.0
        l = fonte.ler()
        self.assertTrue(l.apagado)
        jogo.nave.control.activate_next_stage()
        l = fonte.ler()
        self.assertFalse(l.apagado)
        self.assertFalse(l.motor_abaixo)

    def test_estagios_confere_com_os_da_nave_simulada(self):
        jogo, fonte = self.criar()
        jogo.nave.control.activate_next_stage()
        jogo.nave.control.throttle = 1.0
        jogo.avancar(3.0)
        obtidos = fonte.estagios()
        esperados = jogo.sim.estagios()
        self.assertEqual(len(obtidos), len(esperados))
        for obtido, esperado in zip(obtidos, esperados):
            for campo in dataclasses.fields(esperado):
                with self.subTest(campo=campo.name):
                    self.assertAlmostEqual(
                        getattr(obtido, campo.name) / getattr(esperado, campo.name), 1.0, delta=1e-6
                    )

    def test_executar_liga_o_piloto_automatico_e_desliga_o_sas(self):
        jogo, fonte = self.criar()
        nave = jogo.nave
        fonte.executar(Comando(acelerador=0.7, pitch=80.0, rumo=45.0))
        self.assertFalse(nave.control.sas)
        self.assertTrue(nave.control.rcs)
        self.assertTrue(math.isnan(nave.auto_pilot.target_roll))
        self.assertTrue(nave.auto_pilot.engajado)
        self.assertEqual(nave.auto_pilot.reference_frame, SUP)
        self.assertEqual(nave.control.throttle, 0.7)
        self.assertEqual((nave.auto_pilot.pitch, nave.auto_pilot.heading), (80.0, 45.0))
        self.assertEqual(nave.control.current_stage, 2)
        fonte.executar(Comando(acelerador=1.0, pitch=90.0, rumo=90.0, estagiar=True))
        self.assertEqual(nave.control.current_stage, 1)
        self.assertTrue(jogo.sim.aceso)
        self.assertEqual(jogo.procedimentos, [])

    def test_piloto_automatico_com_o_servidor_0_5(self):
        jogo, fonte = self.criar()
        jogo.nave.auto_pilot.servidor_antigo = True
        fonte.executar(Comando(acelerador=1.0))
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
        fonte.executar(Comando(acelerar_ate=500.0))
        self.assertEqual(jogo.space_center.warps, [500.0])
        self.assertAlmostEqual(jogo.sim.t, 500.0)
        fonte.executar(Comando(acelerar_ate=100.0))
        self.assertEqual(jogo.space_center.warps, [500.0])

    def test_sem_warp_o_aviso_sai_uma_vez_so(self):
        jogo, fonte = self.criar()
        jogo.space_center.warp_proibido = True
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            fonte.executar(Comando(acelerar_ate=500.0))
            fonte.executar(Comando(acelerar_ate=600.0))
        self.assertEqual(saida.getvalue().count("AVISO"), 1)
        self.assertEqual(jogo.sim.t, 0.0)

    def test_liberar_faz_cada_passo_por_si(self):
        jogo, fonte = self.criar()
        fonte.executar(Comando(acelerador=1.0))
        jogo.nave.auto_pilot.quebrado = True
        fonte.liberar()
        self.assertEqual(jogo.nave.control.throttle, 0.0)
        self.assertTrue(jogo.nave.control.sas)
        self.assertTrue(all(f.removido for f in jogo.fluxos))

    def test_plano_do_alvo(self):
        jogo, fonte = self.criar()
        n, nome, problema = fonte.alvo()
        self.assertIsNone(n)
        self.assertIsNone(nome)
        self.assertIn("nenhum alvo", problema)

        n_alvo = plano_com_janela(jogo.sim, 1_200.0, 10.0)
        jogo.space_center.target_vessel = jogo.alvo_com_plano(n_alvo, "Estação")
        n, nome, problema = fonte.alvo()
        self.assertIsNone(problema)
        self.assertEqual(nome, "Estação")
        self.assertLess(angulo(n, n_alvo), 1e-6)

        jogo.space_center.target_vessel = None
        jogo.space_center.target_body = jogo.alvo_com_plano(n_alvo, "Mun")
        n, nome, problema = fonte.alvo()
        self.assertLess(angulo(n, n_alvo), 1e-6)

        outro = jogo.alvo_com_plano(n_alvo, "Duna")
        outro.orbit = types.SimpleNamespace(body=object())
        jogo.space_center.target_body = outro
        n, nome, problema = fonte.alvo()
        self.assertIsNone(n)
        self.assertEqual(nome, "Duna")
        self.assertIn("não orbita", problema)

    def test_voo_completo_pelo_kRPC_nos_dois_sentidos_do_referencial(self):
        for canhoto in (True, False):
            with self.subTest(canhoto=canhoto):
                jogo, fonte = self.criar(canhoto=canhoto)
                guiagem = Guiagem(fonte.corpo, 80_000.0, 45.0, ler_estagios=fonte.estagios)
                for _ in range(PASSOS_MAX):
                    comando = guiagem.passo(fonte.ler())
                    if guiagem.fase in (ORBITA, FALHA):
                        break
                    fonte.executar(comando)
                    jogo.avancar(DT)
                self.assertEqual(guiagem.fase, ORBITA)
                l = jogo.sim.leitura()
                self.assertAlmostEqual(inclinacao_de(KERBIN, l.r, l.v), 45.0, delta=0.5)
                _, _, ra, rp = elementos(KERBIN, l.r, l.v)
                self.assertTrue(78_500.0 < rp - KERBIN.raio < ra - KERBIN.raio < 81_500.0)
                self.assertTrue(jogo.space_center.warps)


class TestSubir(unittest.TestCase):
    def test_sobe_ate_a_orbita_e_deixa_a_nave_livre(self):
        jogo = JogoFalso()
        tela = TelaFalsa()
        original = subida.NaveKrpc.executar

        def executar(fonte, comando):
            original(fonte, comando)
            jogo.avancar(subida.INTERVALO)

        with sem_espera():
            with mock.patch.object(subida.NaveKrpc, "executar", executar):
                codigo = subida.subir(jogo, argumentos(), tela)
        self.assertEqual(codigo, subida.EM_ORBITA)
        valores = valores_sub(tela.pacotes[-1])
        self.assertEqual(valores["FASE"], "ORBITA")
        self.assertEqual(jogo.nave.control.throttle, 0.0)
        self.assertTrue(jogo.nave.control.sas)
        self.assertFalse(jogo.nave.auto_pilot.engajado)
        self.assertTrue(all(f.removido for f in jogo.fluxos))
        for pacote in tela.pacotes:
            self.assertTrue(all(len(linha) <= 31 and linha.isascii() for linha in pacote))

    def sem_voar(self, jogo, **extras):
        tela = TelaFalsa()
        with sem_espera() as saida:
            codigo = subida.subir(jogo, argumentos(**extras), tela)
        return codigo, tela, saida.getvalue()

    def test_altitude_dentro_do_ar_nao_decola(self):
        jogo = JogoFalso()
        codigo, tela, texto = self.sem_voar(jogo, altitude=50_000.0)
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertIn("altitude", texto)
        valores = valores_sub(tela.pacotes[-1])
        self.assertEqual(valores["AVISO"], "ALTITUDE")
        self.assertEqual(valores["FASE"], "FALHA")
        self.assertTrue(jogo.sim.pousada)
        self.assertEqual(jogo.nave.control.throttle, 0.0)
        self.assertEqual(jogo.nave.control.current_stage, 2)

    def test_altitude_minima_sem_ar_e_maior_que_a_do_chao(self):
        jogo = JogoFalso(NaveSimulada.mun())
        codigo, tela, _ = self.sem_voar(jogo, altitude=5_000.0)
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertEqual(valores_sub(tela.pacotes[-1])["AVISO"], "ALTITUDE")

    def test_plano_do_alvo_sem_alvo_nao_decola(self):
        jogo = JogoFalso()
        codigo, tela, texto = self.sem_voar(jogo, plano_do_alvo=True)
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertEqual(valores_sub(tela.pacotes[-1])["AVISO"], "ALVO")
        self.assertTrue(jogo.sim.pousada)

    def test_plano_do_alvo_de_outro_planeta_nao_decola(self):
        jogo = JogoFalso()
        alvo = jogo.alvo_com_plano(plano_com_janela(jogo.sim, 1_200.0, 10.0), "Duna")
        alvo.orbit = types.SimpleNamespace(body=object())
        jogo.space_center.target_body = alvo
        codigo, tela, texto = self.sem_voar(jogo, plano_do_alvo=True)
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertEqual(valores_sub(tela.pacotes[-1])["AVISO"], "ALVO")
        self.assertIn("Duna", texto)

    def test_nave_no_ar_nao_sobe(self):
        jogo = JogoFalso()
        jogo.sim.pousada = False
        codigo, tela, texto = self.sem_voar(jogo)
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertIn("parada no chão", texto)
        self.assertEqual(tela.pacotes, [])

    def test_eixos_errados_nao_decolam(self):
        jogo = JogoFalso(leste_errado=True)
        codigo, tela, texto = self.sem_voar(jogo)
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertIn("ERRO", texto)
        self.assertEqual(jogo.nave.control.current_stage, 2)

    def test_plano_do_alvo_escolhido_no_jogo(self):
        jogo = JogoFalso()
        n_alvo = plano_com_janela(jogo.sim, 1_200.0, 10.0)
        jogo.space_center.target_vessel = jogo.alvo_com_plano(n_alvo)
        original = subida.NaveKrpc.executar

        def executar(fonte, comando):
            original(fonte, comando)
            jogo.avancar(subida.INTERVALO)

        tela = TelaFalsa()
        with sem_espera() as saida:
            with mock.patch.object(subida.NaveKrpc, "executar", executar):
                codigo = subida.subir(jogo, argumentos(plano_do_alvo=True), tela)
        self.assertEqual(codigo, subida.EM_ORBITA)
        l = jogo.sim.leitura()
        self.assertLess(angulo(unit(cruz(l.r, l.v)), n_alvo), 0.1)
        self.assertIn("erro de plano", saida.getvalue())
        fases = [valores_sub(p)["FASE"] for p in tela.pacotes]
        self.assertIn("JANELA", fases)
        self.assertIn("PLANO", fases)

    def test_ctrl_c_no_meio_do_warp_corta_o_motor(self):
        jogo = JogoFalso()
        original = subida.NaveKrpc.executar

        def executar(fonte, comando):
            original(fonte, comando)
            jogo.avancar(subida.INTERVALO)

        def interromper(ut):
            raise KeyboardInterrupt

        jogo.space_center.warp_to = interromper
        with sem_espera():
            with mock.patch.object(subida.NaveKrpc, "executar", executar):
                with self.assertRaises(KeyboardInterrupt):
                    subida.subir(jogo, argumentos(), TelaFalsa())
        self.assertEqual(jogo.nave.control.throttle, 0.0)
        self.assertTrue(jogo.nave.control.sas)
        self.assertFalse(jogo.nave.auto_pilot.engajado)
        self.assertTrue(all(f.removido for f in jogo.fluxos))


class ReceptorUdp:
    """Escuta numa porta livre do 127.0.0.1 e guarda cada pacote com o instante em que chegou."""

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.settimeout(0.05)
        self.porta = self.socket.getsockname()[1]
        self.pacotes = []
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._rodar, daemon=True)
        self._thread.start()

    def _rodar(self):
        while not self._parar.is_set():
            try:
                dados, _ = self.socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            self.pacotes.append((time.monotonic(), dados.decode("ascii").split("\n")))

    def fechar(self):
        self._parar.set()
        self._thread.join()
        self.socket.close()


class TestBatimentoNoWarp(unittest.TestCase):
    def test_a_tela_recebe_linhas_durante_o_warp_com_a_janela_descendo(self):
        jogo = JogoFalso()
        jogo.space_center.duracao_warp = 0.5
        n_alvo = plano_com_janela(jogo.sim, 7_200.0, 30.0)
        fonte = subida.NaveKrpc(jogo, jogo.nave, jogo.corpo, subida.corpo_do_jogo(jogo.corpo))
        guiagem = Guiagem(fonte.corpo, 80_000.0, 0.0, n_alvo=n_alvo, ler_estagios=fonte.estagios)
        original = subida.NaveKrpc.executar

        def executar(nave_krpc, comando):
            original(nave_krpc, comando)
            jogo.avancar(subida.INTERVALO)

        threads_antes = threading.active_count()
        receptor = ReceptorUdp()
        tela = subida.TelaSubida(f"127.0.0.1:{receptor.porta}")
        try:
            with sem_espera():
                with mock.patch.object(subida.NaveKrpc, "executar", executar):
                    codigo = subida.conduzir(fonte, guiagem, fonte.corpo, tela)
            dormir(0.2)
        finally:
            tela.fechar()
            receptor.fechar()
        self.assertEqual(codigo, subida.EM_ORBITA)
        self.assertEqual(len(jogo.space_center.intervalos_de_warp), len(jogo.space_center.warps))
        self.assertGreaterEqual(len(jogo.space_center.intervalos_de_warp), 2)

        primeiro_inicio, primeiro_fim = jogo.space_center.intervalos_de_warp[0]
        durante = [
            valores_sub(linhas)
            for instante, linhas in receptor.pacotes
            if primeiro_inicio <= instante <= primeiro_fim
        ]
        self.assertGreaterEqual(len(durante), 3)
        janelas = [int(v["JAN"]) for v in durante]
        self.assertTrue(all(v["FASE"] == "JANELA" for v in durante))
        self.assertEqual(janelas, sorted(janelas, reverse=True))
        self.assertGreater(janelas[0] - janelas[-1], 1_000)
        self.assertLess(janelas[-1], 7_200 - 1_000)

        for intervalo in jogo.space_center.intervalos_de_warp[1:]:
            enviados = [p for instante, p in receptor.pacotes if intervalo[0] <= instante <= intervalo[1]]
            self.assertGreaterEqual(len(enviados), 3)

        janela_toda = [int(valores_sub(linhas)["JAN"]) for _, linhas in receptor.pacotes if valores_sub(linhas)["FASE"] == "JANELA"]
        self.assertEqual(janela_toda, sorted(janela_toda, reverse=True))
        for _, linhas in receptor.pacotes:
            self.assertTrue(all(len(linha) <= 31 and linha.isascii() for linha in linhas))
        self.assertEqual(threading.active_count(), threads_antes)

    def test_com_a_nave_simulada_o_warp_e_instantaneo_e_nao_deixa_thread_para_tras(self):
        nave = NaveSimulada.kerbin()
        n_alvo = plano_com_janela(nave, 1_200.0, 10.0)
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0, n_alvo=n_alvo, ler_estagios=nave.estagios)
        tela = TelaFalsa()
        threads_antes = threading.active_count()
        with sem_espera():
            codigo = subida.conduzir(subida.FonteSimulada(nave), guiagem, KERBIN, tela, repeticoes=4)
        self.assertEqual(codigo, subida.EM_ORBITA)
        self.assertEqual(threading.active_count(), threads_antes)
        janelas = [int(valores_sub(p)["JAN"]) for p in tela.pacotes if valores_sub(p)["FASE"] == "JANELA"]
        self.assertEqual(janelas, sorted(janelas, reverse=True))

    def test_batimento_para_se_a_leitura_do_ut_falhar(self):
        class FonteQueFalha:
            def ut_agora(self):
                raise RuntimeError("a conexão caiu")

        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0)
        tela = TelaFalsa()
        with subida.Batimento(FonteQueFalha(), guiagem, KERBIN, tela, nave.leitura()):
            dormir(0.05)
        self.assertEqual(tela.pacotes, [])

    def test_sem_warp_nao_liga_a_thread(self):
        nave = NaveSimulada.kerbin()
        guiagem = Guiagem(KERBIN, 80_000.0, 0.0)
        tela = TelaFalsa()
        fonte = subida.FonteSimulada(nave)
        with mock.patch.object(subida, "Batimento", side_effect=AssertionError("não devia ligar")):
            l = fonte.ler()
            self.assertIs(subida.executar_mostrando(fonte, Comando(), l, guiagem, KERBIN, tela), l)


class TestMain(unittest.TestCase):
    def rodar(self, *opcoes):
        with sem_espera() as saida:
            with mock.patch.object(sys, "argv", ["subida.py", "--tela", "127.0.0.1:9", *opcoes]):
                codigo = subida.main()
        return codigo, saida.getvalue()

    def test_demo_chega_em_orbita(self):
        codigo, texto = self.rodar("--demo")
        self.assertEqual(codigo, subida.EM_ORBITA)
        self.assertIn("Em órbita", texto)
        self.assertIn("--> COSTA", texto)
        self.assertRegex(texto, r"--> GIRO a .*, giro de [0-9.]+°")
        self.assertRegex(texto, r"pitch +[-0-9.]+  nariz +[-0-9.]+  rumo")

    def test_demo_com_plano_do_alvo_passa_pela_janela_e_iguala_o_plano(self):
        codigo, texto = self.rodar("--demo", "--plano-do-alvo")
        self.assertEqual(codigo, subida.EM_ORBITA)
        for fase in ("JANELA", "DECOLAGEM", "PLANO", "ORBITA"):
            self.assertIn(f"--> {fase}", texto)
        erro = float(re.search(r"erro de plano ([0-9.]+)", texto).group(1))
        self.assertLess(erro, 0.1)

    def test_demo_com_inclinacao_e_altitude(self):
        codigo, texto = self.rodar("--demo", "--altitude", "100000", "--inclinacao", "45")
        self.assertEqual(codigo, subida.EM_ORBITA)
        inclinacao = float(re.search(r"inclinação ([0-9.]+)°", texto).group(1))
        self.assertAlmostEqual(inclinacao, 45.0, delta=0.5)

    def test_demo_recusa_altitude_dentro_do_ar(self):
        codigo, texto = self.rodar("--demo", "--altitude", "50000")
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertIn("Não vou decolar", texto)

    def test_ctrl_c_devolve_130(self):
        with mock.patch.object(subida, "subir_demo", side_effect=KeyboardInterrupt):
            codigo, texto = self.rodar("--demo")
        self.assertEqual(codigo, subida.INTERROMPIDO)
        self.assertEqual(subida.INTERROMPIDO, 130)

    def test_krpc_conecta_sem_esperar_e_fecha_a_conexao(self):
        jogo = JogoFalso()
        chamadas = []

        def conectar_krpc(address, *dispositivos, esperar=True):
            chamadas.append((address, dispositivos, esperar))
            return jogo

        falsa = types.SimpleNamespace(conectar_krpc=conectar_krpc)
        original = subida.NaveKrpc.executar

        def executar(fonte, comando):
            original(fonte, comando)
            jogo.avancar(subida.INTERVALO)

        with mock.patch.dict(sys.modules, {"ponte": falsa}):
            with mock.patch.object(subida.NaveKrpc, "executar", executar):
                codigo, _ = self.rodar("10.0.0.5")
        self.assertEqual(codigo, subida.EM_ORBITA)
        self.assertEqual(chamadas, [("10.0.0.5", (), False)])
        self.assertTrue(jogo.fechada)

    def test_nave_perdida_devolve_nao_chegou(self):
        jogo = JogoFalso()
        falsa = types.SimpleNamespace(conectar_krpc=lambda address, *d, esperar=True: jogo)
        with mock.patch.dict(sys.modules, {"ponte": falsa}):
            with mock.patch.object(Guiagem, "passo", side_effect=RuntimeError("a nave explodiu")):
                codigo, texto = self.rodar()
        self.assertEqual(codigo, subida.NAO_CHEGOU)
        self.assertIn("Perdi a nave", texto)
        self.assertTrue(jogo.fechada)
        self.assertEqual(jogo.nave.control.throttle, 0.0)
        self.assertTrue(jogo.nave.control.sas)


if __name__ == "__main__":
    unittest.main()
