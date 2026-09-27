"""Fly by wire de avião: o manche escolhe para onde ir, e o avião vai.

O manche não mexe nas superfícies. Ele move um ponto na navball, o ponto do
FBW, que diz para onde o piloto quer ir: um rumo e um ângulo de subida. O
script inclina as asas, puxa ou cede o nariz e usa o leme até o pró-grado
(para onde o avião vai de verdade) ficar em cima do ponto. Soltando o
manche, o ponto fica onde está e o avião vai até ele e segue nele.

- Manche para trás ou para a frente: o ponto sobe ou desce.
- Manche para os lados: o ponto anda para os lados, ou seja, muda o rumo.
- Manche solto com o ponto a menos de TRAVA_GAMA do horizonte: o avião trava
  a altitude daquele momento e corrige o ponto sozinho para ficar nela.
- No chão, ou com o FBW desligado pelo botão, o manche mexe direto nas
  superfícies (lei direta), como no jogo sem o script.
- Piloto automático, por cima do ponto (ligado pelo painel de sistemas, pela
  ponte da tela): HDG põe o rumo do ponto no rumo escolhido; V/S põe o ângulo
  de subida que dá a velocidade vertical escolhida; ALT sobe ou desce até a
  altitude escolhida (armado) e segura nela (ligado). Mexer o manche para os
  lados desliga o HDG; para trás ou para a frente, o ALT e o V/S.
- Proteções: inclinação das asas até INCLINACAO_MAX, ângulo de subida entre
  GAMA_MIN e GAMA_MAX e ângulo de ataque até ALFA_MAX: puxar o manche não
  estola o avião.
- O acelerador fica com o piloto: a alavanca do joystick passa direto para o
  jogo quando é mexida, e as teclas do jogo continuam valendo.

Por dentro, três camadas, cada uma pedindo algo para a de baixo:
 1. Trajetória: a diferença entre o ponto e o pró-grado vira a aceleração que
    falta para curvar o caminho. Dela saem a inclinação das asas e a carga
    (quantos g a asa tem que fazer).
 2. Carga → velocidade de giro do nariz em pitch; inclinação → velocidade de
    giro em roll; o leme zera o escorregamento (curva coordenada).
 3. Velocidade de giro → superfícies (control.pitch, roll e yaw), com o
    ganho dividido pela aceleração angular que o avião consegue fazer agora.
    Assim o mesmo ajuste serve devagar e rápido, e em aviões diferentes.

A guiagem (FlyByWire) não conhece o kRPC nem o joystick: recebe uma Leitura e
um Manche e devolve Comandos. Os testes (tests/test_fbw.py) usam a mesma
guiagem com um avião simulado.

O ponto aparece na navball da tela multifunção (bridge/mfd.py), se ela
estiver aberta: o script manda FBW <pitch> <rumo> por UDP para a ponte da
tela, que repassa para a tela, junto com a lei, a trava e os modos do piloto
automático. A ponte responde com os toques do painel de sistemas (os korry
FBW e TRAVA ALT e os modos do piloto) e os valores escolhidos no menu. Sem a
ponte aberta, nada acontece. Protocolo em docs/protocolo.md.

Uso:
    python scripts/fbw.py                    # KSP e tela neste computador
    python scripts/fbw.py 192.168.1.10       # KSP em outro computador
    python scripts/fbw.py --tela 192.168.1.20  # ponte da tela em outro computador
    python scripts/fbw.py --controles        # mostra os eixos e botões do joystick, sem o KSP
    python scripts/fbw.py --perfil xbox      # controle de Xbox no lugar do Extreme 3D Pro
    python scripts/fbw.py --sem-joystick     # sem joystick: decola pelo teclado, e o piloto automático voa
    python scripts/fbw.py --gravar voo.csv   # grava o voo numa planilha, para ajustar os ganhos

Deixe os eixos do joystick sem nada nas configurações de controle do KSP,
senão o jogo também lê o manche e os comandos chegam em dobro.
Ctrl+C devolve o controle ao piloto. Roteiro de testes em docs/fbw.md.
"""

import argparse
import csv
import math
import os
import socket
import sys
import time
from dataclasses import dataclass

# ---- o ponto e o manche ----
VEL_PONTO_PITCH = 8.0    # graus/s: o ponto sobe ou desce com o manche todo para trás ou para a frente
VEL_PONTO_RUMO = 15.0    # graus/s: o ponto anda para os lados com o manche todo de lado
LADO_MAX = 60.0          # graus: o ponto fica no máximo isso de lado do pró-grado, para não sair da navball
ZONA_MORTA = 0.05        # manche: fração do curso no centro que conta como solto
EXPO = 0.4               # manche: 0 = resposta reta; perto de 1, mais fina perto do centro
TRAVA_GAMA = 1.0         # graus: com o manche solto e o ponto mais perto que isso do horizonte, trava a altitude

# ---- proteções ----
GAMA_MIN, GAMA_MAX = -30.0, 30.0   # graus: ângulo de subida do ponto
INCLINACAO_MAX = 60.0    # graus: inclinação das asas
ALFA_MAX = 15.0          # graus: ângulo de ataque máximo (a maioria das asas do KSP estola bem depois)
ALFA_MIN = -8.0          # graus: ângulo de ataque mínimo, empurrando o manche
CARGA_MIN, CARGA_MAX = 0.0, 4.0    # g: o que a asa pode fazer
MARGEM_CARGA = 0.9       # a inclinação só usa 90% da carga que a asa aguenta, para sobrar para corrigir
ALFA_CONTA_CARGA = 2.0   # graus: com menos ângulo de ataque que isso, sobra asa (a estimativa não vale)
TAU_CARGA_MAXIMA = 0.5   # s: filtro da estimativa de quanto a asa aguenta

# ---- camada 1: trajetória ----
K_TRAJETORIA = 0.4       # 1/s: o pró-grado anda até o ponto com constante de tempo de 2,5 s
GIRO_TRAJETORIA_MAX = math.radians(5.0)  # rad/s: o caminho sobe ou desce no máximo 5°/s
K_ALTITUDE = 0.15        # 1/s: com a altitude travada, 10 m de erro pedem 1,5 m/s de subida
VV_TRAVA_MAX = 10.0      # m/s: a correção da altitude travada sobe ou desce no máximo isso
A_CIMA_MIN = 0.3         # g: a inclinação é calculada com pelo menos esta carga, para não virar de costas

# ---- camada 2: velocidades de giro ----
K_CARGA = 1.5            # quanto a diferença de carga acelera o giro do nariz (sem unidade)
K_ALFA = 2.0             # 1/s: na proteção, o ângulo de ataque volta para o limite com constante de 0,5 s
GIRO_PITCH_MAX = math.radians(20.0)  # rad/s
K_INCLINACAO = 2.0       # 1/s: 10° de diferença na inclinação pedem 20°/s de roll
GIRO_ROLL_MAX = math.radians(45.0)   # rad/s
K_BETA = 4.0             # 1/s²: o leme contra o escorregamento
K_YAW = 3.0              # 1/s: amortecimento do yaw

# ---- camada 3: superfícies ----
KP_PITCH, KI_PITCH = 6.0, 12.0   # 1/s e 1/s²: da diferença na velocidade de giro para a aceleração angular pedida
KP_ROLL = 5.0            # 1/s
KI_ROLL = 2.0            # 1/s²: só perto da inclinação pedida, para o aileron que o avião torto precisa
INTEGRA_ROLL = math.radians(5.0)   # rad: mais longe que isso, o integral do roll fica parado
AUTORIDADE_MIN = 0.2     # rad/s²: abaixo disso, o que o jogo informa é ruído (evita dividir por quase zero)

# ---- piloto automático: HDG, ALT e V/S ----
VV_ALT_PADRAO = 10.0     # m/s: com o ALT armado e o V/S desligado, sobe ou desce com isso
ALT_CAPTURA_MIN = 20.0   # m: o ALT assume (nivela) a menos disso da altitude escolhida...
ALT_CAPTURA_TEMPO = 4.0  # s: ...ou a menos de 4 s dela, na velocidade vertical de agora
MODOS_AP = ("HDG", "ALT", "VS")

# ---- acelerador automático (SPD): ainda sem interface; fica desligado ----
KP_ACELERADOR, KI_ACELERADOR = 0.1, 0.02   # por m/s e por m (m/s × s)

# ---- quando o FBW assume ----
TEMPO_DECOLAGEM = 1.0    # s no ar antes de o FBW assumir (um pulo na pista não conta)
PRESSAO_MIN = 500.0      # Pa: abaixo disso (ar ralo, ou avião quase parado) as superfícies não seguram nada
V_MIN = 20.0             # m/s
DT_MAX = 0.2             # s: um passo maior que isso (jogo pausado, travada) não entra nas contas

# ---- laço, tela e terminal ----
INTERVALO = 0.02         # s: até 50 voltas por segundo, a mesma taxa da física do KSP
INTERVALO_TELA = 0.1     # s: o ponto vai para a tela 10 vezes por segundo, como os outros marcadores
INTERVALO_STATUS = 1.0   # s
PORTA_TELA = 50100       # UDP: a ponte da tela (bridge/mfd.py) escuta aqui
MAX_PACOTE = 512         # bytes: um pacote da ponte da tela, com algumas linhas
MUDANCA_MIN = 0.002      # não reenvia ao jogo um comando que quase não mudou
ACELERADOR_MUDOU = 0.01  # a alavanca só vai para o jogo depois de se mexer isso

FBW = "FBW"              # leis de controle
DIRETA = "DIRETA"


@dataclass
class Perfil:
    """Onde está cada controle no joystick (números do pygame, a partir de 0)."""
    roll: int
    pitch: int
    yaw: int              # None: sem leme no manche (o FBW coordena a curva sozinho)
    acelerador: int       # None: acelerador só pelas teclas do jogo
    botao_fbw: int        # liga e desliga o FBW


PERFIS = {
    # Logitech Extreme 3D Pro (hardware/construcao.md): X, Y, torção e a
    # alavanca da base. O botão do FBW é o "3", no topo do manche.
    "extreme3d": Perfil(roll=0, pitch=1, yaw=2, acelerador=3, botao_fbw=2),
    # Controle de Xbox: o manche no analógico esquerdo, o leme no direito e o
    # FBW no botão Y. A ordem dos eixos muda com o sistema: confira com --controles.
    "xbox": Perfil(roll=0, pitch=1, yaw=2, acelerador=None, botao_fbw=3),
}


@dataclass
class Leitura:
    pitch: float          # graus: nariz acima do horizonte
    rumo: float           # graus: para onde o nariz aponta, 0 = norte, 90 = leste
    rolagem: float        # graus: positiva com a asa direita para baixo
    velocidade: tuple     # m/s: (cima, norte, leste), em relação ao chão (no KSP não há vento)
    altitude: float       # m acima do mar
    pressao: float        # Pa: pressão dinâmica, ½ · densidade · v²
    forca_aero: tuple     # N: (cima, norte, leste), sustentação + arrasto
    massa: float          # kg
    g: float              # m/s²: gravidade na altitude da nave
    autoridade: tuple     # rad/s²: aceleração angular com o comando todo, em (pitch, roll, yaw)
    no_chao: bool
    ut: float             # s: tempo do jogo


@dataclass
class Manche:
    pitch: float = 0.0    # -1 a 1; positivo = puxado (nariz para cima)
    roll: float = 0.0     # positivo = para a direita
    yaw: float = 0.0      # positivo = para a direita
    acelerador: float = None  # 0 a 1; None se a alavanca não se mexeu desde a última leitura


@dataclass
class Comandos:
    pitch: float
    roll: float
    yaw: float
    acelerador: float     # None: não mexe no acelerador do jogo


# ---- contas com vetores (cima, norte, leste) ----

def escalar(a, b):
    return sum(x * y for x, y in zip(a, b))


def modulo(v):
    return math.sqrt(escalar(v, v))


def limitar(x, minimo, maximo):
    return max(minimo, min(maximo, x))


def angulo180(graus):
    """O mesmo ângulo entre -180 e 180."""
    return (graus + 180.0) % 360.0 - 180.0


def base_da_nave(pitch, rumo, rolagem):
    """Os eixos da nave (frente, direita, cima) em (cima, norte, leste); ângulos em graus.

    A mesma conta de bridge/navball.py, que foi conferida com a navball do
    jogo, só com os eixos na ordem do kRPC. Sem rolagem, a direita fica na
    horizontal; rolar para a direita abaixa a asa direita.
    """
    p, r, o = math.radians(pitch), math.radians(rumo), math.radians(rolagem)
    sp, cp = math.sin(p), math.cos(p)
    sr, cr = math.sin(r), math.cos(r)
    so, co = math.sin(o), math.cos(o)
    frente = (sp, cp * cr, cp * sr)
    direita0 = (0.0, -sr, cr)
    cima0 = (cp, -sp * cr, -sp * sr)
    direita = tuple(co * d - so * c for d, c in zip(direita0, cima0))
    cima = tuple(so * d + co * c for d, c in zip(direita0, cima0))
    return frente, direita, cima


def direcao(vetor):
    """(ângulo acima do horizonte, rumo) do vetor (cima, norte, leste), em graus."""
    cima, norte, leste = vetor
    gama = math.degrees(math.asin(limitar(cima / modulo(vetor), -1.0, 1.0)))
    return gama, math.degrees(math.atan2(leste, norte)) % 360.0


def angulos_do_ar(velocidade, base):
    """Ângulo de ataque e escorregamento, em radianos.

    Ataque: quanto o nariz está acima do movimento, no plano das asas.
    Escorregamento: positivo quando o avião anda para a direita do nariz.
    """
    frente, direita, cima = base
    vf = escalar(velocidade, frente)
    return (
        math.atan2(-escalar(velocidade, cima), vf),
        math.atan2(escalar(velocidade, direita), vf),
    )


def curva(x):
    """Manche → comando: zona morta no centro e resposta mais fina perto dele."""
    if abs(x) <= ZONA_MORTA:
        return 0.0
    x = limitar(math.copysign((abs(x) - ZONA_MORTA) / (1.0 - ZONA_MORTA), x), -1.0, 1.0)
    return (1.0 - EXPO) * x + EXPO * x**3


class FlyByWire:
    """Decide as superfícies a cada leitura. Não conhece o kRPC nem o joystick."""

    def __init__(self):
        self.ligado = True           # botão do FBW; mesmo ligado, no chão a lei é a direta
        self.lei = DIRETA
        self.motivo = "no chão"      # por que a lei é a direta
        self.ponto = None            # (ângulo de subida, rumo) em graus: onde o piloto pôs o ponto
        self.comando = None          # o que o FBW persegue: o ponto, corrigido pela trava de altitude
        self.altitude_travada = None  # m
        self.velocidade_alvo = None  # m/s: acelerador automático (SPD); None = acelerador na mão
        self.ap = dict.fromkeys(MODOS_AP, False)        # modos do piloto automático ligados
        self.ap_valores = dict.fromkeys(MODOS_AP, None)  # rumo (graus), altitude (m), velocidade vertical (m/s)
        self.alt_capturada = False   # o ALT chegou na altitude e segura nela
        self._sem_trava_auto = False  # a trava foi solta no korry: não trava sozinho até o manche mexer
        self.taxas = (0.0, 0.0, 0.0)  # rad/s: giro medido em pitch, roll e yaw
        self.diagnostico = {}        # o que cada camada pediu, para o terminal e a gravação
        self._no_ar_desde = None     # ut da decolagem
        self._anterior = None        # (ut, base) da leitura anterior
        self._integral = {"pitch": 0.0, "roll": 0.0, "acelerador": 0.0}
        self._saida = Comandos(0.0, 0.0, 0.0, None)
        self._carga_maxima = None    # g: quanto a asa aguenta antes de ALFA_MAX, filtrado
        self._pedido_trava = False   # o korry TRAVA ALT pediu para travar na próxima volta

    def passo(self, l, m):
        base = base_da_nave(l.pitch, l.rumo, l.rolagem)
        dt = self._medir_taxas(l, base)
        lei, self.motivo = self._escolher_lei(l)
        if lei != self.lei:
            self._trocar_lei(lei, l)
        if lei == DIRETA:
            saida = Comandos(curva(m.pitch), curva(m.roll), curva(m.yaw), m.acelerador)
        else:
            saida = self._voar(l, m, base, dt)
        self._saida = saida
        return saida

    # ---- piloto automático e trava, pelo painel ----

    @property
    def no_chao(self):
        """No chão, ou no primeiro segundo depois de sair dele (um pulo na pista não conta)."""
        return self._no_ar_desde is None or self.motivo == "no chão"

    def estado_ap(self, nome):
        """0 desligado, 1 ligado, 2 armado (o ALT indo até a altitude)."""
        if not self.ap[nome]:
            return 0
        return 2 if nome == "ALT" and not self.alt_capturada else 1

    def definir(self, nome, valor):
        """O valor escolhido no menu: rumo em graus, altitude em m, velocidade vertical em m/s."""
        if nome == "HDG":
            valor %= 360.0
        if nome == "ALT" and valor != self.ap_valores["ALT"]:
            self.alt_capturada = False   # altitude nova: vai até ela de novo
        self.ap_valores[nome] = valor

    def alternar_modo(self, nome):
        """Liga ou desliga um modo. Só liga voando na lei do FBW."""
        if self.ap[nome]:
            self.ap[nome] = False
        elif self.lei == FBW:
            self.ap[nome] = True
            if nome == "ALT":
                self.alt_capturada = False
            if nome in ("ALT", "VS"):
                self.altitude_travada = None   # o piloto automático cuida da subida
        return self.ap[nome]

    def alternar_trava(self):
        """Korry TRAVA ALT: trava a altitude do momento, ou solta. Só voando na lei do FBW."""
        if self.lei != FBW:
            return
        if self.altitude_travada is not None:
            self.altitude_travada = None
            self._sem_trava_auto = True
        else:
            self._pedido_trava = True
            self.ap["ALT"] = self.ap["VS"] = False

    # ---- leis ----

    def _escolher_lei(self, l):
        if l.no_chao:
            self._no_ar_desde = None
        elif self._no_ar_desde is None:
            self._no_ar_desde = l.ut
        if not self.ligado:
            return DIRETA, "FBW desligado no botão"
        if self._no_ar_desde is None or l.ut - self._no_ar_desde < TEMPO_DECOLAGEM:
            return DIRETA, "no chão"
        if l.pressao < PRESSAO_MIN or modulo(l.velocidade) < V_MIN:
            return DIRETA, "ar ralo ou devagar demais para as superfícies"
        return FBW, ""

    def _trocar_lei(self, lei, l):
        self.lei = lei
        self.altitude_travada = None
        self._pedido_trava = self._sem_trava_auto = False
        if lei == DIRETA:
            # Sem o FBW, não há ponto: o piloto automático desliga, como no avião.
            self.ponto = self.comando = None
            self.ap = dict.fromkeys(MODOS_AP, False)
            return
        # O ponto começa onde o avião já está indo, e os integradores com o
        # comando que já estava no jogo: a troca não dá tranco.
        gama, rumo = direcao(l.velocidade)
        self.ponto = self.comando = (limitar(gama, GAMA_MIN, GAMA_MAX), rumo)
        self._carga_maxima = None
        self._integral = {
            "pitch": self._saida.pitch,
            "roll": self._saida.roll,
            "acelerador": self._saida.acelerador or 0.0,
        }

    # ---- medidas ----

    def _medir_taxas(self, l, base):
        """Velocidades de giro pela diferença entre esta leitura e a anterior.

        Pelos eixos da própria nave, e não pelos ângulos: o rumo e a rolagem
        pulam de 359° para 0°, e a rolagem se mistura com o yaw quando o
        nariz sobe. Devolve o passo de tempo do jogo; 0 se o jogo não andou.
        """
        anterior, self._anterior = self._anterior, (l.ut, base)
        if anterior is None:
            return 0.0
        ut0, base0 = anterior
        dt = l.ut - ut0
        if dt <= 0.0:
            self._anterior = anterior  # leitura repetida: mede na próxima
            return 0.0
        if dt > DT_MAX:
            return 0.0
        frente, direita, cima = base
        frente0, direita0, cima0 = base0
        d_frente = tuple(a - b for a, b in zip(frente, frente0))
        d_direita = tuple(a - b for a, b in zip(direita, direita0))
        cima_m = tuple((a + b) / 2 for a, b in zip(cima, cima0))
        direita_m = tuple((a + b) / 2 for a, b in zip(direita, direita0))
        self.taxas = (
            escalar(d_frente, cima_m) / dt,       # pitch: o nariz vai para o "cima" da nave
            -escalar(d_direita, cima_m) / dt,     # roll: a asa direita desce
            escalar(d_frente, direita_m) / dt,    # yaw: o nariz vai para a direita
        )
        return dt

    # ---- a lei do FBW ----

    def _mover_ponto(self, l, m, dt, rumo_trajetoria):
        gama, rumo = self.ponto
        puxa, lado = curva(m.pitch), curva(m.roll)
        # Mexer no manche devolve o ponto ao piloto, no eixo que ele mexeu.
        if puxa != 0.0:
            self.altitude_travada = None
            self._sem_trava_auto = False
            self.ap["ALT"] = self.ap["VS"] = False
        if lado != 0.0:
            self.ap["HDG"] = False
        gama = limitar(gama + VEL_PONTO_PITCH * puxa * dt, GAMA_MIN, GAMA_MAX)
        rumo += VEL_PONTO_RUMO * lado * dt
        if self.ap["HDG"]:
            rumo = self._valor("HDG", rumo_trajetoria)
        # Longe demais para o lado, o ponto sairia da navball: fica na beirada
        # e vai sendo levado pelo avião enquanto ele vira.
        lado_do_progrado = limitar(angulo180(rumo - rumo_trajetoria), -LADO_MAX, LADO_MAX)
        rumo = (rumo_trajetoria + lado_do_progrado) % 360.0
        subindo = self.ap["ALT"] or self.ap["VS"]
        if self._pedido_trava or (
            puxa == 0.0 and self.altitude_travada is None and not subindo
            and not self._sem_trava_auto and abs(gama) < TRAVA_GAMA
        ):
            self.altitude_travada = l.altitude
            self._pedido_trava = False
            gama = 0.0
        self.ponto = (gama, rumo)

    def _valor(self, nome, atual):
        """O valor escolhido para o modo; sem valor, fica o de agora."""
        if self.ap_valores[nome] is None:
            self.ap_valores[nome] = atual
        return self.ap_valores[nome]

    def _subida_do_piloto(self, l, v):
        """Velocidade vertical pedida pelo ALT e pelo V/S, em m/s, ou None se nenhum está ligado."""
        vs = self._valor("VS", 0.0) if self.ap["VS"] else None
        if not self.ap["ALT"]:
            return vs
        erro = self._valor("ALT", l.altitude) - l.altitude
        if not self.alt_capturada and abs(erro) <= max(ALT_CAPTURA_MIN, abs(l.velocidade[0]) * ALT_CAPTURA_TEMPO):
            # Chegou: nivela e segura, e o V/S termina, como no avião.
            self.alt_capturada = True
            self.ap["VS"] = False
        if self.alt_capturada:
            return limitar(K_ALTITUDE * erro, -VV_TRAVA_MAX, VV_TRAVA_MAX)
        if vs is not None:
            return vs
        return math.copysign(VV_ALT_PADRAO, erro)

    def _voar(self, l, m, base, dt):
        v = modulo(l.velocidade)
        gama, rumo = direcao(l.velocidade)
        self._mover_ponto(l, m, dt, rumo)

        gama_c, rumo_c = self.ponto
        subida = self._subida_do_piloto(l, v)
        if subida is not None:
            # O ponto fica no ângulo de subida do piloto automático: soltar o
            # modo mexendo no manche começa dali, sem tranco.
            gama_c = limitar(math.degrees(math.asin(limitar(subida / v, -1.0, 1.0))), GAMA_MIN, GAMA_MAX)
            self.ponto = (gama_c, rumo_c)
        elif self.altitude_travada is not None:
            subida = limitar(K_ALTITUDE * (self.altitude_travada - l.altitude), -VV_TRAVA_MAX, VV_TRAVA_MAX)
            gama_c = math.degrees(math.asin(limitar(subida / v, -1.0, 1.0)))
        self.comando = (gama_c, rumo_c)

        # O que a asa está fazendo agora.
        g = l.g
        frente, direita, cima = base
        alfa, beta = angulos_do_ar(l.velocidade, base)
        carga = escalar(l.forca_aero, cima) / (l.massa * g)
        phi = math.radians(l.rolagem)
        inclinacao_max = self._inclinacao_maxima(carga, alfa, dt)

        # 1. Trajetória: quanto o caminho tem que girar para cima e para o
        # lado, e a aceleração que a asa precisa fazer para isso (a gravidade
        # puxa o caminho para baixo, então a asa soma g · cos γ).
        cos_gama = math.cos(math.radians(gama))
        giro_gama = limitar(
            K_TRAJETORIA * math.radians(gama_c - gama), -GIRO_TRAJETORIA_MAX, GIRO_TRAJETORIA_MAX
        )
        giro_rumo = K_TRAJETORIA * math.radians(angulo180(rumo_c - rumo))
        a_cima = v * giro_gama + g * cos_gama
        a_lado = v * cos_gama * giro_rumo
        inclinacao_c = math.degrees(math.atan2(a_lado, max(a_cima, A_CIMA_MIN * g)))
        inclinacao_c = limitar(inclinacao_c, -inclinacao_max, inclinacao_max)
        # A carga é a que segura a parte de cima com a inclinação de agora: na
        # curva, a asa tem que puxar mais para o avião não descer.
        cos_inclinacao = max(math.cos(math.radians(l.rolagem)), math.cos(math.radians(70.0)))
        carga_c = limitar(a_cima / (g * cos_inclinacao), CARGA_MIN, CARGA_MAX)

        # 2. Pitch: a carga vira giro do nariz. Com a carga certa, o nariz
        # gira junto com o caminho (a primeira parte); se falta carga, gira
        # mais rápido para aumentar o ângulo de ataque (a segunda).
        giro_caminho = g * (carga - cos_gama * math.cos(phi)) / v
        giro_pitch_c = g * (carga_c - cos_gama * math.cos(phi)) / v + K_CARGA * (carga_c - carga) * g / v
        # Proteção do ângulo de ataque: perto do limite, o nariz só gira o
        # bastante para o ângulo parar no limite.
        giro_pitch_c = min(giro_pitch_c, giro_caminho + K_ALFA * (math.radians(ALFA_MAX) - alfa))
        giro_pitch_c = max(giro_pitch_c, giro_caminho + K_ALFA * (math.radians(ALFA_MIN) - alfa))
        giro_pitch_c = limitar(giro_pitch_c, -GIRO_PITCH_MAX, GIRO_PITCH_MAX)

        # Roll: vai até a inclinação pedida, girando mais devagar perto dela.
        erro_inclinacao = math.radians(angulo180(inclinacao_c - l.rolagem))
        giro_roll_c = limitar(K_INCLINACAO * erro_inclinacao, -GIRO_ROLL_MAX, GIRO_ROLL_MAX)

        # 3. Superfícies.
        giro_pitch, giro_roll, giro_yaw = self.taxas
        a_pitch, a_roll, a_yaw = (max(a, AUTORIDADE_MIN) for a in l.autoridade)
        pitch = self._pi("pitch", giro_pitch_c - giro_pitch, a_pitch, dt, KP_PITCH, KI_PITCH)
        # O integral do roll soma a diferença na inclinação, e não no giro, e
        # só perto dela: se somasse durante a rolagem, o aileron guardado
        # levaria a asa além da inclinação pedida.
        passo = KI_ROLL * erro_inclinacao / a_roll * dt if abs(erro_inclinacao) < INTEGRA_ROLL else 0.0
        roll = self._integrar("roll", passo, KP_ROLL * (giro_roll_c - giro_roll) / a_roll, -1.0, 1.0)
        # Yaw: na curva coordenada o nariz gira em yaw g · sen φ / v, e o
        # avião não escorrega de lado.
        giro_yaw_c = g * math.sin(phi) / v
        yaw = limitar((K_BETA * beta + K_YAW * (giro_yaw_c - giro_yaw)) / a_yaw, -1.0, 1.0)

        self.diagnostico = {
            "inclinacao_c": inclinacao_c,
            "inclinacao_max": inclinacao_max,
            "carga_c": carga_c,
            "carga": carga,
            "alfa": math.degrees(alfa),
            "beta": math.degrees(beta),
            "giro_pitch_c": math.degrees(giro_pitch_c),
            "giro_roll_c": math.degrees(giro_roll_c),
        }
        return Comandos(pitch, roll, yaw, self._acelerador(l, m, v, dt))

    def _inclinacao_maxima(self, carga, alfa, dt):
        """Até onde as asas podem inclinar sem o avião descer.

        Inclinado, o avião precisa de 1 / cos(inclinação) g para não descer: 2 g
        a 60°. Devagar, a asa pode não chegar lá antes de ALFA_MAX, e a
        proteção seguraria o ângulo de ataque com o avião perdendo altura.
        Então a inclinação fica no que a asa aguenta, e a curva fica mais
        aberta. A sustentação cresce mais ou menos junto com o ângulo de
        ataque, então a asa aguenta carga · ALFA_MAX / alfa; com o ângulo de
        ataque pequeno, sobra asa e a conta não vale.
        """
        alfa = math.degrees(alfa)
        estimativa = carga * ALFA_MAX / alfa if alfa > ALFA_CONTA_CARGA else CARGA_MAX
        estimativa = limitar(estimativa, 0.0, CARGA_MAX)
        if self._carga_maxima is None:
            self._carga_maxima = estimativa
        else:
            self._carga_maxima += (estimativa - self._carga_maxima) * min(1.0, dt / TAU_CARGA_MAXIMA)
        carga_livre = self._carga_maxima * MARGEM_CARGA
        if carga_livre <= 1.0:
            return 0.0
        return min(INCLINACAO_MAX, math.degrees(math.acos(1.0 / carga_livre)))

    def _pi(self, eixo, erro, autoridade, dt, kp, ki):
        """Proporcional + integral, em fração do comando todo.

        O ganho é uma aceleração angular por diferença de giro; dividir pela
        autoridade converte em comando. O integral guarda o comando que
        segura o avião parado no giro pedido (ex.: o profundor para manter o
        ângulo de ataque) e não cresce enquanto o comando estiver no limite.
        """
        return self._integrar(eixo, ki * erro / autoridade * dt, kp * erro / autoridade, -1.0, 1.0)

    def _acelerador(self, l, m, v, dt):
        """Na mão do piloto, ou segurando velocidade_alvo (SPD, ainda sem interface)."""
        if self.velocidade_alvo is None:
            return m.acelerador
        erro = self.velocidade_alvo - v
        return self._integrar("acelerador", KI_ACELERADOR * erro * dt, KP_ACELERADOR * erro, 0.0, 1.0)

    def _integrar(self, nome, passo, proporcional, minimo, maximo):
        """Soma o passo ao integral e devolve integral + proporcional, entre minimo e maximo.

        Com a saída no limite, o integral só anda no sentido de sair dele:
        senão ele cresceria à toa e depois demoraria a voltar.
        """
        integral = self._integral[nome]
        novo = limitar(integral + passo, minimo, maximo)
        saida = novo + proporcional
        if minimo <= saida <= maximo or (saida > maximo and novo < integral) or (saida < minimo and novo > integral):
            self._integral[nome] = integral = novo
        return limitar(integral + proporcional, minimo, maximo)


# ---- o jogo ----

class NaveKrpc:
    """Lê o avião pelo kRPC, com streams, e monta a Leitura para o FBW."""

    def __init__(self, conn, nave):
        space_center = conn.space_center
        self.nave = nave
        self.corpo = corpo = nave.orbit.body
        self._gm = corpo.gravitational_parameter
        self._raio = corpo.equatorial_radius
        situacao = space_center.VesselSituation
        self._no_chao = (situacao.landed, situacao.splashed, situacao.pre_launch)

        # Atitude no horizonte da nave, como a tela multifunção. Velocidade e
        # força do ar num referencial "híbrido": em relação ao chão, que gira
        # com o planeta, escritas nos eixos do horizonte (cima, norte, leste).
        superficie = nave.surface_reference_frame
        referencial = space_center.ReferenceFrame.create_hybrid(
            position=corpo.reference_frame, rotation=superficie
        )
        atitude = nave.flight(superficie)
        voo = nave.flight(referencial)
        stream = conn.add_stream
        self._streams = {
            "pitch": stream(getattr, atitude, "pitch"),
            "rumo": stream(getattr, atitude, "heading"),
            "rolagem": stream(getattr, atitude, "roll"),
            "velocidade": stream(getattr, voo, "velocity"),
            "altitude": stream(getattr, voo, "mean_altitude"),
            "pressao": stream(getattr, voo, "dynamic_pressure"),
            "forca_aero": stream(getattr, voo, "aerodynamic_force"),
            "massa": stream(getattr, nave, "mass"),
            "torque": stream(getattr, nave, "available_torque"),
            "inercia": stream(getattr, nave, "moment_of_inertia"),
            "situacao": stream(getattr, nave, "situation"),
            "ut": stream(getattr, space_center, "ut"),
            "sas": stream(getattr, nave.control, "sas"),
        }

    def ler(self):
        s = {nome: stream() for nome, stream in self._streams.items()}
        # Torque disponível: (positivo, negativo) em volta dos eixos da nave,
        # que são pitch, roll e yaw, na mesma ordem da inércia.
        positivo, negativo = s["torque"]
        autoridade = tuple(
            (abs(mais) + abs(menos)) / 2 / max(inercia, 1e-6)
            for mais, menos, inercia in zip(positivo, negativo, s["inercia"])
        )
        return Leitura(
            pitch=s["pitch"],
            rumo=s["rumo"],
            rolagem=s["rolagem"],
            velocidade=s["velocidade"],
            altitude=s["altitude"],
            pressao=s["pressao"],
            forca_aero=s["forca_aero"],
            massa=s["massa"],
            g=self._gm / (self._raio + s["altitude"]) ** 2,
            autoridade=autoridade,
            no_chao=s["situacao"] in self._no_chao,
            ut=s["ut"],
        )

    def sas_ligado(self):
        return self._streams["sas"]()

    def remover(self):
        for stream in self._streams.values():
            stream.remove()


class Controles:
    """Manda os comandos ao jogo, só quando mudam: cada um é uma ida e volta pela rede."""

    def __init__(self, controle):
        self._controle = controle
        self._enviados = {}
        self._livre = False

    def mandar(self, c, livre=False):
        """livre: sem joystick e na lei direta. O manche fica com o teclado do
        jogo: a primeira vez solta o que o FBW tinha pedido, e depois não
        manda mais nada até o FBW assumir de novo."""
        if livre:
            if not self._livre:
                self.soltar()
                self._enviados = {}
                self._livre = True
            return
        self._livre = False
        for nome in ("pitch", "roll", "yaw", "acelerador"):
            valor = getattr(c, nome)
            if valor is None:
                continue
            anterior = self._enviados.get(nome)
            if anterior is None or abs(valor - anterior) > MUDANCA_MIN or (valor == 0.0 and anterior != 0.0):
                setattr(self._controle, "throttle" if nome == "acelerador" else nome, valor)
                self._enviados[nome] = valor

    def soltar(self):
        """Devolve o manche ao piloto. O acelerador fica como está."""
        for nome in ("pitch", "roll", "yaw"):
            setattr(self._controle, nome, 0.0)


# ---- o joystick ----

class Joystick:
    """Lê o joystick pelo pygame e devolve um Manche a cada leitura."""

    def __init__(self, perfil, indice=0):
        # Sem isso, o SDL ignora o joystick enquanto a janela do KSP estiver na frente.
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        self._pygame = pygame
        # A fila de eventos, que atualiza o joystick, precisa do sistema de
        # vídeo, mas nenhuma janela é aberta. Sem monitor (Pi pela rede), o
        # driver "dummy" serve.
        try:
            pygame.display.init()
        except pygame.error:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            pygame.display.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() <= indice:
            sys.exit("Nenhum joystick encontrado. Ligue o joystick na USB e confira com --controles.")
        self._j = pygame.joystick.Joystick(indice)
        self._j.init()
        self.nome = self._j.get_name()
        self._perfil = perfil
        pygame.event.pump()
        self._acelerador_enviado = self._ler_acelerador()
        self._botao = False

    def _eixo(self, numero):
        if numero is None or numero >= self._j.get_numaxes():
            return 0.0
        return self._j.get_axis(numero)

    def _ler_acelerador(self):
        if self._perfil.acelerador is None:
            return None
        return (1.0 - self._eixo(self._perfil.acelerador)) / 2  # para a frente (-1 no SDL) = tudo

    def ler(self):
        """Devolve (Manche, apertou o botão do FBW nesta leitura)."""
        self._pygame.event.pump()
        p = self._perfil
        acelerador = self._ler_acelerador()
        if acelerador is not None and abs(acelerador - self._acelerador_enviado) > ACELERADOR_MUDOU:
            self._acelerador_enviado = acelerador
        else:
            # Só vai para o jogo quando a alavanca se mexe: parada, as teclas
            # do jogo continuam mudando o acelerador.
            acelerador = None
        botao = p.botao_fbw < self._j.get_numbuttons() and bool(self._j.get_button(p.botao_fbw))
        apertou, self._botao = botao and not self._botao, botao
        # No SDL, puxar o manche para trás dá +1: nariz para cima.
        manche = Manche(self._eixo(p.pitch), self._eixo(p.roll), self._eixo(p.yaw), acelerador)
        return manche, apertou

    def mostrar(self):
        """Modo --controles: mostra os eixos e os botões apertados, ao vivo."""
        j = self._j
        print(f"{self.nome}: {j.get_numaxes()} eixos, {j.get_numbuttons()} botões. Ctrl+C para sair.")
        while True:
            self._pygame.event.pump()
            eixos = " ".join(f"{i}:{j.get_axis(i):+.2f}" for i in range(j.get_numaxes()))
            botoes = " ".join(str(i) for i in range(j.get_numbuttons()) if j.get_button(i)) or "-"
            print(f"\reixos {eixos}   botões {botoes:12}", end="", flush=True)
            time.sleep(0.05)


class SemJoystick:
    """No lugar do joystick (--sem-joystick): o manche fica sempre solto.

    Na lei direta, o avião é pilotado pelo teclado do jogo (decolagem e
    pouso). No ar, o FBW segura o ponto, e quem mexe nele é o piloto
    automático, pelo painel de sistemas (a página de botões da ponte da tela).
    """

    nome = "nenhum (--sem-joystick: teclado na lei direta, piloto automático no FBW)"
    manche_livre = True

    def ler(self):
        return Manche(), False


# ---- a tela e a gravação ----

def linhas_de_estado(fbw):
    """O estado do FBW nas linhas do protocolo da tela (docs/protocolo.md):
    o ponto, a lei, a trava e os modos do piloto automático."""
    if fbw is None or fbw.lei != FBW:
        ponto = "FBW OFF"
    else:
        pitch, rumo = fbw.comando
        ponto = f"FBW {round(pitch * 10)} {round(rumo * 10) % 3600}"
    if fbw is None:
        return [ponto, "LEI OFF", "TRAVA OFF"] + [f"APL {nome} 0" for nome in MODOS_AP]
    if fbw.lei == FBW:
        lei = "FBW"
    else:
        lei = "CHAO" if fbw.no_chao else "DIRETA"
    trava = "OFF" if fbw.altitude_travada is None else str(round(fbw.altitude_travada))
    return [ponto, f"LEI {lei}", f"TRAVA {trava}"] + [f"APL {nome} {fbw.estado_ap(nome)}" for nome in MODOS_AP]


def executar(linha, fbw):
    """Executa uma linha da ponte da tela: um toque do painel de sistemas ou
    um valor do menu do piloto. Devolve um texto para o terminal, ou None."""
    partes = linha.split()
    if len(partes) == 2 and partes[0] == "CMD":
        nome = partes[1]
        if nome == "FBW":
            fbw.ligado = not fbw.ligado
            return f"Painel: FBW {'ligado' if fbw.ligado else 'desligado (lei direta)'}"
        if nome == "TRAVA":
            fbw.alternar_trava()
            return "Painel: trava de altitude"
        if nome in MODOS_AP:
            ligado = fbw.alternar_modo(nome)
            return f"Painel: {nome} {'ligado' if ligado else 'desligado'}"
    if len(partes) == 3 and partes[0] == "APV" and partes[1] in MODOS_AP:
        try:
            valor = int(partes[2])
        except ValueError:
            return f"Linha desconhecida da ponte: {linha[:40]}"
        fbw.definir(partes[1], valor / 10 if partes[1] == "VS" else float(valor))
        return None
    return f"Linha desconhecida da ponte: {linha[:40]}"


class TelaFbw:
    """Conversa com a ponte da tela (bridge/mfd.py), por UDP.

    Manda o ponto, a lei, a trava e os modos do piloto automático, nas linhas
    do protocolo da tela (docs/protocolo.md), num pacote só. A ponte responde
    para o endereço de onde o pacote veio, com os toques do painel de
    sistemas e os valores do menu. Se a ponte não estiver aberta, os pacotes
    se perdem e nada acontece.
    """

    def __init__(self, endereco):
        self._destino = (endereco, PORTA_TELA)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Uma porta fixa desde já: no Windows, ler de um socket sem porta dá erro.
        self._socket.bind(("", 0))
        self._socket.setblocking(False)

    def enviar(self, fbw):
        """fbw: a FlyByWire, ou None quando o script está saindo."""
        pacote = "\n".join(linhas_de_estado(fbw))
        try:
            self._socket.sendto(pacote.encode("ascii"), self._destino)
        except OSError:
            pass  # a tela é opcional

    def receber(self):
        """As linhas que a ponte mandou desde a última chamada."""
        linhas = []
        while True:
            try:
                dados, _ = self._socket.recvfrom(MAX_PACOTE)
            except OSError:
                # Nada na fila, ou, no Windows, o aviso de que um pacote
                # anterior não achou a ponte.
                return linhas
            linhas += dados.decode("ascii", errors="replace").split("\n")


class Gravador:
    """Grava cada volta numa planilha (CSV), para ver a resposta do avião e ajustar os ganhos."""

    COLUNAS = (
        "ut", "lei", "manche_pitch", "manche_roll", "ponto_gama", "ponto_rumo",
        "comando_gama", "comando_rumo", "gama", "rumo", "altitude", "velocidade",
        "pitch", "rolagem", "inclinacao_c", "alfa", "beta", "carga", "carga_c",
        "giro_pitch", "giro_pitch_c", "giro_roll", "giro_roll_c", "giro_yaw",
        "cmd_pitch", "cmd_roll", "cmd_yaw", "pressao",
        "autoridade_pitch", "autoridade_roll", "autoridade_yaw",
    )

    def __init__(self, caminho):
        self._arquivo = open(caminho, "w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._arquivo)
        self._csv.writerow(self.COLUNAS)
        self._proximo_flush = 0.0

    def gravar(self, l, m, c, fbw):
        gama, rumo = direcao(l.velocidade) if modulo(l.velocidade) > 0 else (0.0, 0.0)
        ponto = fbw.ponto or (None, None)
        comando = fbw.comando or (None, None)
        d = fbw.diagnostico if fbw.lei == FBW else {}
        linha = (
            l.ut, fbw.lei, m.pitch, m.roll, *ponto, *comando, gama, rumo, l.altitude,
            modulo(l.velocidade), l.pitch, l.rolagem, d.get("inclinacao_c"), d.get("alfa"),
            d.get("beta"), d.get("carga"), d.get("carga_c"),
            math.degrees(fbw.taxas[0]), d.get("giro_pitch_c"), math.degrees(fbw.taxas[1]),
            d.get("giro_roll_c"), math.degrees(fbw.taxas[2]),
            c.pitch, c.roll, c.yaw, l.pressao, *l.autoridade,
        )
        self._csv.writerow("" if x is None else round(x, 4) if isinstance(x, float) else x for x in linha)
        agora = time.monotonic()
        if agora >= self._proximo_flush:
            self._arquivo.flush()
            self._proximo_flush = agora + 1.0

    def fechar(self):
        self._arquivo.close()


class SemGravacao:
    def gravar(self, *args):
        pass

    def fechar(self):
        pass


def status(l, fbw, c):
    gama, rumo = direcao(l.velocidade) if modulo(l.velocidade) > 0 else (0.0, 0.0)
    texto = (
        f"{fbw.lei:6} vel {modulo(l.velocidade):5.0f} m/s  alt {l.altitude:6.0f} m  "
        f"pro-grado {gama:+5.1f} {rumo:5.1f}"
    )
    if fbw.lei == FBW:
        d = fbw.diagnostico
        trava = f"  trava {fbw.altitude_travada:.0f} m" if fbw.altitude_travada is not None else ""
        modos = " ".join(
            f"{nome}{'*' if fbw.estado_ap(nome) == 2 else ''}" for nome in MODOS_AP if fbw.ap[nome]
        )
        trava += f"  piloto {modos}" if modos else ""
        texto += (
            f"  ponto {fbw.comando[0]:+5.1f} {fbw.comando[1]:5.1f}{trava}"
            f"  inclinacao {l.rolagem:+4.0f}/{d['inclinacao_c']:+4.0f}"
            f"  alfa {d['alfa']:4.1f}  carga {d['carga']:4.2f}/{d['carga_c']:4.2f} g"
        )
    else:
        texto += f"  ({fbw.motivo})"
    return texto + f"  comandos {c.pitch:+.2f} {c.roll:+.2f} {c.yaw:+.2f}"


def voar(conn, nave, joystick, tela, gravador):
    """Pilota a nave até ela deixar de ser a ativa."""
    fonte = NaveKrpc(conn, nave)
    controles = Controles(nave.control)
    fbw = FlyByWire()
    print(f"Nave: {nave.name} ({fonte.corpo.name}). FBW ligado: assume depois da decolagem.")
    lei = None
    proxima_tela = proxima_verificacao = 0.0
    try:
        while True:
            l = fonte.ler()
            m, apertou = joystick.ler()
            if apertou:
                fbw.ligado = not fbw.ligado
                print(f"Botão: FBW {'ligado' if fbw.ligado else 'desligado (lei direta)'}")
            for linha in tela.receber():
                texto = executar(linha.strip(), fbw) if linha.strip() else None
                if texto:
                    print(texto)
            c = fbw.passo(l, m)
            controles.mandar(c, livre=getattr(joystick, "manche_livre", False) and fbw.lei == DIRETA)
            gravador.gravar(l, m, c, fbw)

            agora = time.monotonic()
            if fbw.lei != lei:
                lei = fbw.lei
                print(f"--> lei {lei}" + (f" ({fbw.motivo})" if fbw.motivo else ""))
            if agora >= proxima_tela:
                tela.enviar(fbw)
                proxima_tela = agora + INTERVALO_TELA
            if agora >= proxima_verificacao:
                # O SAS do KSP brigaria com o FBW pelo manche.
                if fbw.lei == FBW and fonte.sas_ligado():
                    nave.control.sas = False
                    print("SAS desligado: quem segura o avião agora é o FBW.")
                print(status(l, fbw, c))
                if conn.space_center.active_vessel != nave:
                    return
                proxima_verificacao = agora + INTERVALO_STATUS
            time.sleep(INTERVALO)
    finally:
        tela.enviar(None)
        try:
            controles.soltar()
            fonte.remover()
        except (ValueError, RuntimeError):
            pass  # a nave pode não existir mais


def esperar_nave(conn, joystick):
    """Espera a cena de voo e devolve a nave ativa. Enquanto isso, o joystick é lido e descartado."""
    avisou = False
    while True:
        try:
            return conn.space_center.active_vessel
        except (ValueError, RuntimeError):
            if not avisou:
                print("Nenhuma nave ativa. Aguardando a cena de voo...")
                avisou = True
        fim = time.monotonic() + 1.0
        while time.monotonic() < fim:
            joystick.ler()
            time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "address",
        nargs="?",
        default="127.0.0.1",
        help="IP do computador onde o KSP está rodando (padrão: este computador)",
    )
    parser.add_argument(
        "--tela",
        default="127.0.0.1",
        metavar="IP",
        help="IP do computador da ponte da tela, bridge/mfd.py (padrão: este computador)",
    )
    parser.add_argument(
        "--perfil",
        choices=sorted(PERFIS),
        default="extreme3d",
        help="onde ficam os eixos e o botão do FBW no joystick (padrão: extreme3d)",
    )
    parser.add_argument("--joystick", type=int, default=0, metavar="N", help="qual joystick usar, se houver mais de um")
    parser.add_argument("--controles", action="store_true", help="só mostra os eixos e os botões do joystick, sem o KSP")
    parser.add_argument(
        "--sem-joystick",
        action="store_true",
        help="sem joystick: na lei direta, o teclado do jogo; no FBW, o piloto automático pelo painel",
    )
    parser.add_argument("--gravar", metavar="ARQUIVO", help="grava o voo numa planilha CSV")
    args = parser.parse_args()

    if args.sem_joystick and args.controles:
        sys.exit("--controles mostra o joystick: não dá para usar junto com --sem-joystick.")
    joystick = SemJoystick() if args.sem_joystick else Joystick(PERFIS[args.perfil], args.joystick)
    if args.controles:
        try:
            joystick.mostrar()
        except KeyboardInterrupt:
            print()
        return
    print(f"Joystick: {joystick.nome}" + ("" if args.sem_joystick else f" (perfil {args.perfil})"))

    # Os scripts ficam em scripts/ e a ponte em bridge/, que tem a conexão com o kRPC.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
    from ponte import conectar_krpc

    conn = conectar_krpc(args.address)
    tela = TelaFbw(args.tela)
    gravador = Gravador(args.gravar) if args.gravar else SemGravacao()
    try:
        while True:
            nave = esperar_nave(conn, joystick)
            try:
                voar(conn, nave, joystick, tela, gravador)
            except (ValueError, RuntimeError) as e:
                print(f"Perdi a nave (explodiu ou o jogo saiu da cena de voo): {e}")
    except KeyboardInterrupt:
        print("\nInterrompido: o manche volta para o piloto.")
    finally:
        gravador.fechar()
        conn.close()


if __name__ == "__main__":
    main()
