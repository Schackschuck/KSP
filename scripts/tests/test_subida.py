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

import dataclasses
import math
import os
import sys
import unittest
from dataclasses import dataclass

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


def inclinacao_de(corpo, r, v):
    n = unit(cruz(r, v))
    return math.degrees(math.acos(ponto(n, corpo.polo)))


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


def plano_com_janela(nave, atraso, inclinacao, sentido=1):
    """O normal de um plano que passa pela base daqui a `atraso` segundos."""
    corpo = nave.corpo
    r_futuro = rotacionar(nave.r, corpo.polo, corpo.omega * atraso)
    i = math.radians(inclinacao)
    leste = unit(cruz(corpo.polo, r_futuro))
    direcao = soma(esc(math.cos(i), leste), esc(sentido * math.sin(i), corpo.polo))
    return unit(cruz(unit(r_futuro), direcao))


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


if __name__ == "__main__":
    unittest.main()
