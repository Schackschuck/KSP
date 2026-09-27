"""Ponte kRPC ⇄ tela multifunção: navball, telemetria e botões de toque.

A tela (a mikromedia for ARM, 320x240 com touch) só desenha o que recebe;
toda a conta que envolve o jogo fica aqui. Enquanto o firmware da placa não
existe, a tela é um simulador numa janela do PC (mfd_simulador.py) ou uma
página no navegador do celular (mfd_celular.py). As três falam o mesmo
protocolo. Protocolo em docs/protocolo.md; roteiro em docs/mfd.md.

Uso:
    python mfd.py                    # KSP neste computador, tela simulada
    python mfd.py --demo             # sem o KSP: a nave se mexe sozinha
    python mfd.py 192.168.1.10       # KSP em outro computador
    python mfd.py --zoom 3           # janela do simulador maior
    python mfd.py --celular          # a tela no navegador do celular, pelo Wi-Fi
    python mfd.py --celular 8080     # idem, noutra porta (padrão: 8000)
    python mfd.py --porta COM7       # a mikromedia de verdade, quando o firmware existir
    python mfd.py --painel 8002      # a página de botões do painel noutra porta (padrão: 8001)
    python mfd.py --sem-painel       # sem a página de botões

Os scripts de voo também podem pôr um marcador na navball: o fly by wire
(scripts/fbw.py) manda o ponto para onde o avião vai, por UDP, e esta ponte
repassa para a tela.

O painel de sistemas de controle (modos do SAS, SAS, RCS, FBW e o piloto
automático) também é tratado aqui, em sistemas.py: enquanto o painel não
existe, uma página de botões no navegador (celular/painel.html) manda as
mesmas linhas. Apertar um modo abre a roda do SAS na tela, e mexer no
encoder abre a página do piloto automático; uns 10 s depois, a tela volta
para a navball.
"""

import argparse
import math
import socket
import sys
import time
from dataclasses import dataclass

import serial

from ponte import Painel, conectar_krpc, esperar_nave
from sistemas import Remetente, Sistemas

INTERVALO_ATITUDE = 0.05  # s: navball 20 vezes por segundo
INTERVALO_MARCADORES = 0.1  # s: as direções dos marcadores no mundo mudam devagar
INTERVALO_NUMEROS = 0.1   # s: altitude e velocidade; também servem de "estou vivo"
INTERVALO_ORBITA = 0.5    # s: apoastro e periastro mudam devagar
REENVIO_ESTADOS = 1.0     # s: reenvia os estados mesmo sem mudança, por segurança
VERIFICA_NAVE = 1.0       # s: de quanto em quanto tempo conferir se a nave ou o planeta mudou
VEL_MIN_MARCADOR = 0.5    # m/s: abaixo disso a direção do movimento é só ruído
DIST_MIN_MARCADOR = 1.0   # m: mais perto que isso (acoplado), o marcador do alvo não faz sentido
QUEIMA_MIN_MARCADOR = 0.1  # m/s: queima do nó de manobra que já acabou
SENO_MIN_MARCADOR = 0.01  # normal e radial somem quando a nave anda na vertical (0,6°)
INT32_MAX = 2**31 - 1     # a placa guarda os números em inteiros de 32 bits
PORTA_SCRIPTS = 50100     # UDP: os scripts de voo (scripts/) mandam para cá o que querem na tela
VALIDADE_SCRIPTS = 1.0    # s: sem notícia do script por esse tempo, o marcador dele some
MAX_PACOTE = 512          # bytes: um pacote do fbw.py, com o ponto, a lei, a trava e os modos
RECURSO_MIN = 0.01        # abaixo disso, o recurso acabou (SEM EC, SEM MP)
PORTA_PAINEL = 8001       # a página de botões do painel de sistemas
INTERVALO_LUZES = 0.05    # s: as luzes do painel de sistemas e as páginas dele, 20 vezes por segundo

# Modo do SAS no protocolo → nome do modo no kRPC (SASMode).
MODOS_KRPC = {
    "ESTAB": "stability_assist",
    "MAN": "maneuver",
    "PRO": "prograde",
    "RETRO": "retrograde",
    "NRM": "normal",
    "ANRM": "anti_normal",
    "RFORA": "radial",
    "RDENTRO": "anti_radial",
    "ALVO": "target",
    "AALVO": "anti_target",
}
MODOS_DO_KRPC = {krpc: nome for nome, krpc in MODOS_KRPC.items()}

# Linhas de estado do fbw.py, e o que vale sem ele aberto.
FBW_FECHADO = {
    "LEI": "LEI OFF", "TRAVA": "TRAVA OFF", "ESTOL": "ESTOL 0",
    "APL HDG": "APL HDG 0", "APL ALT": "APL ALT 0", "APL VS": "APL VS 0",
}

# Perto do chão, a altitude passa a ser a do radar (acima do chão, ou do mar).
# Entra abaixo de RADAR_ENTRA e só sai acima de RADAR_SAI: a folga evita
# ficar trocando quando o terreno sobe e desce perto do limite.
RADAR_ENTRA = 5_000  # m
RADAR_SAI = 5_500    # m

# Troca automática entre SUP e ORB, como a navball do KSP: ORB acima de 6% do
# raio do planeta (36 km em Kerbin) e SUP de novo abaixo de 5,5% (33 km).
ORB_SOBE = 0.06
ORB_DESCE = 0.055

# Botões de toque que ligam e desligam sistemas: nome no protocolo →
# propriedade de vessel.control no kRPC. O botão MODO é tratado à parte.
SISTEMAS = {
    "SAS": "sas",
    "RCS": "rcs",
}


@dataclass
class Telemetria:
    pitch: float          # graus acima do horizonte
    rumo: float           # graus: 0 = norte, 90 = leste
    rolagem: float        # graus
    velocidades: dict     # modo → (cima, norte, leste) em m/s; "ALVO" só existe com alvo
    altitude: float       # m acima do nível do mar
    radar: float          # m acima do chão, ou do mar se ele estiver mais perto
    raio_planeta: float   # m
    posicao: tuple        # (cima, norte, leste) da nave em relação ao centro do planeta, em m
    apoastro: float       # m; None numa trajetória de escape
    periastro: float      # m
    tempo_apoastro: float   # s até o apoastro; None numa trajetória de escape
    tempo_periastro: float  # s até o periastro
    acelerador: float     # de 0 a 1
    alvo: str             # nome do alvo escolhido no jogo; None sem alvo
    posicao_alvo: tuple   # (cima, norte, leste) do alvo em relação à nave, em m
    manobra: tuple        # (cima, norte, leste) da queima que falta no próximo nó, em m/s; None sem nó
    sistemas: dict        # {"SAS": True, "RCS": False}
    sas_modo: str = None  # modo do SAS no jogo, um de sistemas.MODOS_SAS
    sem_ec: bool = False  # sem carga elétrica
    sem_mp: bool = False  # sem monopropelente
    erro_sas: float = None  # graus até o marcador; None = a ponte calcula (só a demonstração manda)


def inteiro32(valor):
    return max(-INT32_MAX, min(INT32_MAX, round(valor)))


def decimos(valor):
    """Ângulos e velocidades vão em décimos, como inteiros: 45,3 vira 453."""
    return inteiro32(valor * 10)


def metros(valor):
    """Distância para a tela, ou OFF se não existe ou não cabe em 32 bits
    (acima de 2,1 milhões de km, o que só acontece com planetas distantes)."""
    if valor is None or not math.isfinite(valor) or abs(valor) > INT32_MAX:
        return "OFF"
    return str(round(valor))


def segundos(valor):
    if valor is None or not math.isfinite(valor):
        return "OFF"
    return str(inteiro32(max(0.0, valor)))


def modulo(vetor):
    return math.sqrt(sum(c * c for c in vetor))


def _vetorial(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def normal_e_radial(posicao, velocidade):
    """Direções normal e radial para fora, em (cima, norte, leste), unitárias
    vezes o seno do ângulo entre a posição e a velocidade.

    Normal: perpendicular ao plano da órbita, do lado de onde a nave parece
    girar no sentido anti-horário. Numa órbita para leste, aponta para o norte.
    Radial para fora: no plano da órbita, perpendicular ao movimento, do lado
    de fora do planeta.

    O produto vetorial só dá o sentido certo em eixos "destros", e
    (cima, norte, leste) não é: a conta é feita em (leste, norte, cima).
    Quando a nave anda na vertical, posição e velocidade ficam alinhadas e o
    resultado tende a zero: não existe plano da órbita.
    """
    tamanho = modulo(posicao) * modulo(velocidade)
    if tamanho == 0:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    r = (posicao[2], posicao[1], posicao[0])
    v = (velocidade[2], velocidade[1], velocidade[0])
    normal = tuple(c / tamanho for c in _vetorial(r, v))
    radial = tuple(c / modulo(velocidade) for c in _vetorial(v, normal))
    return (normal[2], normal[1], normal[0]), (radial[2], radial[1], radial[0])


def mensagem_ponto(nome, ponto):
    """<nome> <pitch> <rumo> de um ponto (pitch, rumo) em graus, ou <nome> OFF."""
    if ponto is None:
        return f"{nome} OFF"
    pitch, rumo = ponto
    return f"{nome} {decimos(pitch)} {decimos(rumo) % 3600}"


def mensagem_direcao(nome, vetor, minimo):
    """<nome> <pitch> <rumo> com a direção do vetor (cima, norte, leste),
    ou <nome> OFF se o vetor for curto demais para ter direção."""
    tamanho = modulo(vetor)
    if tamanho < minimo:
        return f"{nome} OFF"
    cima, norte, leste = vetor
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, cima / tamanho))))
    return mensagem_ponto(nome, (pitch, math.degrees(math.atan2(leste, norte))))


def angulo_ate(pitch, rumo, vetor):
    """Graus entre o nariz (pitch, rumo) e a direção do vetor (cima, norte, leste)."""
    tamanho = modulo(vetor)
    if tamanho == 0:
        return None
    p, r = math.radians(pitch), math.radians(rumo)
    nariz = (math.sin(p), math.cos(p) * math.cos(r), math.cos(p) * math.sin(r))
    cosseno = sum(a * b for a, b in zip(nariz, vetor)) / tamanho
    return math.degrees(math.acos(max(-1.0, min(1.0, cosseno))))


def erro_do_sas(t, modo_navball):
    """Graus entre o nariz e o marcador do modo do SAS, ou None.

    O SAS do KSP segue o modo da navball: pró-grado em relação ao chão no
    SUP, à órbita no ORB e ao alvo no ALVO. No ALVO, normal e radial são os
    da órbita. ESTAB não tem marcador: segura a atitude de agora.
    """
    if t.erro_sas is not None:
        return t.erro_sas
    modo = t.sas_modo
    velocidade = t.velocidades.get(modo_navball, t.velocidades["ORB"])
    if modo in ("PRO", "RETRO"):
        vetor = velocidade if modulo(velocidade) >= VEL_MIN_MARCADOR else None
    elif modo in ("NRM", "ANRM", "RFORA", "RDENTRO"):
        base = velocidade if modo_navball != "ALVO" else t.velocidades["ORB"]
        normal, radial = normal_e_radial(t.posicao, base)
        vetor = normal if modo in ("NRM", "ANRM") else radial
        vetor = vetor if modulo(vetor) >= SENO_MIN_MARCADOR else None
    elif modo in ("ALVO", "AALVO"):
        vetor = t.posicao_alvo if t.alvo is not None else None
    elif modo == "MAN":
        vetor = t.manobra
    else:
        return None
    if vetor is None:
        return None
    if modo in ("RETRO", "ANRM", "RDENTRO", "AALVO"):
        vetor = tuple(-c for c in vetor)
    return angulo_ate(t.pitch, t.rumo, vetor)


class ModoNavball:
    """Escolhe o modo da navball como o KSP faz: SUP perto do planeta, ORB
    longe dele e ALVO quando há um alvo escolhido.

    As trocas automáticas só acontecem quando algo muda: a nave cruza a
    altitude de troca ou o alvo muda. Entre uma coisa e outra, vale o que o
    botão MODO escolheu.
    """

    def __init__(self):
        self.modo = None     # None até a primeira leitura
        self._alta = None    # acima da altitude de troca?
        self._alvo = None

    def atualizar(self, t):
        if self._alta is None:
            alta = t.altitude > ORB_SOBE * t.raio_planeta
        elif self._alta:
            alta = t.altitude > ORB_DESCE * t.raio_planeta
        else:
            alta = t.altitude > ORB_SOBE * t.raio_planeta
        cruzou = alta != self._alta
        alvo_mudou = t.alvo != self._alvo
        self._alta, self._alvo = alta, t.alvo

        if self.modo is None or alvo_mudou:
            self.modo = "ALVO" if t.alvo is not None else self._pela_altitude()
        elif cruzou and self.modo != "ALVO":
            self.modo = self._pela_altitude()
        return self.modo

    def alternar(self):
        """Botão MODO: SUP → ORB → ALVO (se houver alvo) → SUP."""
        modos = ["SUP", "ORB"] + (["ALVO"] if self._alvo is not None else [])
        posicao = modos.index(self.modo) if self.modo in modos else -1
        self.modo = modos[(posicao + 1) % len(modos)]

    def _pela_altitude(self):
        return "ORB" if self._alta else "SUP"


class Transmissor:
    """Decide o que mandar para a tela e quando."""

    def __init__(self, tela):
        self.tela = tela
        self.esquecer()

    def esquecer(self):
        """A tela reiniciou ou a nave mudou: tudo vai de novo na próxima volta."""
        self._enviados = {}
        self._proximo = dict.fromkeys(("atitude", "marcadores", "numeros", "orbita", "estados"), 0.0)
        self._radar = False

    def _chegou_a_vez(self, tarefa, intervalo, agora):
        if agora < self._proximo[tarefa]:
            return False
        self._proximo[tarefa] = agora + intervalo
        return True

    def enviar(self, t, modo, agora, ponto_fbw=None):
        """ponto_fbw: (pitch, rumo) do ponto do fly by wire, ou None."""
        enviar = self.tela.enviar

        # 1. Estados. Vão antes dos números: quando o modo muda, a tela apaga
        # os números do modo antigo, e os do modo novo precisam chegar depois.
        if self._enviados.get("MODO") != modo:
            # Modo novo: tudo o que depende dele vai já, sem esperar a vez.
            self._proximo = dict.fromkeys(self._proximo, 0.0)
        reenviar = self._chegou_a_vez("estados", REENVIO_ESTADOS, agora)
        estados = {"MODO": modo}
        estados.update((nome, str(int(ligado))) for nome, ligado in t.sistemas.items())
        for nome, valor in estados.items():
            if reenviar or self._enviados.get(nome) != valor:
                enviar(f"{nome} {valor}")
                self._enviados[nome] = valor

        velocidade = t.velocidades[modo]

        # 2. Navball: a atitude muda rápido; os marcadores são direções fixas
        # no mundo, que a tela reprojeta a cada ATT.
        if self._chegou_a_vez("atitude", INTERVALO_ATITUDE, agora):
            enviar(f"ATT {decimos(t.pitch)} {decimos(t.rumo) % 3600} {decimos(t.rolagem)}")

        if self._chegou_a_vez("marcadores", INTERVALO_MARCADORES, agora):
            enviar(mensagem_direcao("PRO", velocidade, VEL_MIN_MARCADOR))
            # Normal e radial não existem no modo ALVO, como no jogo.
            if modo == "ALVO" or modulo(velocidade) < VEL_MIN_MARCADOR:
                normal = radial = (0.0, 0.0, 0.0)
            else:
                normal, radial = normal_e_radial(t.posicao, velocidade)
            enviar(mensagem_direcao("NRM", normal, SENO_MIN_MARCADOR))
            enviar(mensagem_direcao("RDL", radial, SENO_MIN_MARCADOR))
            posicao_alvo = t.posicao_alvo if t.alvo is not None else (0.0, 0.0, 0.0)
            enviar(mensagem_direcao("TGT", posicao_alvo, DIST_MIN_MARCADOR))
            enviar(mensagem_direcao("MNV", t.manobra or (0.0, 0.0, 0.0), QUEIMA_MIN_MARCADOR))
            enviar(mensagem_ponto("FBW", ponto_fbw))

        # 3. Números. A altitude vai sempre: ela também serve de "estou vivo".
        if self._chegou_a_vez("numeros", INTERVALO_NUMEROS, agora):
            self._radar = t.radar < (RADAR_SAI if self._radar else RADAR_ENTRA)
            if self._radar:
                enviar(f"RAD {inteiro32(t.radar)}")
            else:
                enviar(f"ALT {inteiro32(t.altitude)}")
            enviar(f"VEL {decimos(modulo(velocidade))}")
            enviar(f"VV {decimos(t.velocidades['SUP'][0])}")   # a barra aparece em todo modo
            enviar(f"ACEL {round(100 * max(0.0, min(1.0, t.acelerador)))}")
            if modo == "ALVO":
                enviar(f"DIST {metros(modulo(t.posicao_alvo))}")

        # 4. Órbita: só interessa no modo ORB.
        if modo == "ORB" and self._chegou_a_vez("orbita", INTERVALO_ORBITA, agora):
            enviar(f"AP {metros(t.apoastro)}")
            enviar(f"PE {metros(t.periastro)}")
            enviar(f"TAP {segundos(t.tempo_apoastro)}")
            enviar(f"TPE {segundos(t.tempo_periastro)}")


def _inteiro(texto):
    """O inteiro escrito no texto, ou None. Só aceita dígitos com sinal opcional."""
    corpo = texto[1:] if texto[:1] in ("+", "-") else texto
    return int(texto) if corpo.isascii() and corpo.isdigit() else None


class Scripts:
    """O que os scripts de voo (scripts/) mandam para a tela, por UDP.

    Hoje, só o fly by wire (scripts/fbw.py). Ele manda 10 vezes por segundo,
    num pacote, linhas do próprio protocolo da tela: o ponto (FBW <pitch>
    <rumo> ou FBW OFF), a lei (LEI), a trava de altitude (TRAVA) e os modos
    do piloto automático (APL). A ponte confere cada linha e guarda. Se o
    script parar de mandar (fechou ou travou), tudo volta a OFF em
    VALIDADE_SCRIPTS. As linhas para o fbw.py (os toques do painel de
    sistemas e os valores do menu) vão para o endereço de onde ele mandou.
    """

    def __init__(self, porta=PORTA_SCRIPTS):
        self._fbw = None
        self._estado = dict(FBW_FECHADO)
        self._quando = -math.inf
        self._endereco = None      # de onde o fbw.py manda
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Qualquer rede: o script pode rodar noutro computador (ex.: no PC, com a ponte no Pi).
            self._socket.bind(("", porta))
        except OSError as e:
            print(f"Não foi possível escutar os scripts na porta {porta} (outra ponte aberta?): {e}")
            self._socket.close()
            self._socket = None
            return
        self._socket.setblocking(False)

    def _ler(self):
        while self._socket is not None:
            try:
                dados, endereco = self._socket.recvfrom(MAX_PACOTE)
            except OSError:
                return  # nada na fila (ou, no Windows, um aviso de pacote perdido)
            self._endereco = endereco
            for linha in dados.decode("ascii", errors="replace").split("\n"):
                if linha.strip():
                    self._linha(linha.strip())

    def _linha(self, linha):
        partes = linha.split(" ")
        numeros = [_inteiro(p) for p in partes[1:]]
        if partes == ["FBW", "OFF"]:
            self._fbw, self._quando = None, time.monotonic()
        elif partes[0] == "FBW" and len(numeros) == 2 and None not in numeros and abs(numeros[0]) <= 900:
            self._fbw = (numeros[0] / 10, (numeros[1] / 10) % 360)
            self._quando = time.monotonic()
        elif len(partes) == 2 and partes[0] == "LEI" and partes[1] in ("FBW", "DIRETA", "CHAO", "OFF"):
            self._estado["LEI"] = linha
        elif len(partes) == 2 and partes[0] == "TRAVA" and (partes[1] == "OFF" or numeros[0] is not None):
            self._estado["TRAVA"] = linha
        elif partes in (["ESTOL", "0"], ["ESTOL", "1"]):
            self._estado["ESTOL"] = linha
        elif len(partes) == 3 and partes[0] == "APL" and f"APL {partes[1]}" in self._estado and partes[2] in ("0", "1", "2"):
            self._estado[f"APL {partes[1]}"] = linha
        else:
            print(f"Linha desconhecida de um script: {linha[:40]}")

    def _valido(self):
        return time.monotonic() - self._quando <= VALIDADE_SCRIPTS

    def ponto_fbw(self):
        """(pitch, rumo) do ponto do fly by wire, em graus, ou None."""
        self._ler()
        return self._fbw if self._valido() else None

    def estado_fbw(self):
        """As linhas LEI, TRAVA e APL do fbw.py, ou as de OFF se ele não está mandando."""
        self._ler()
        return dict(self._estado) if self._valido() else dict(FBW_FECHADO)

    def comando_fbw(self, linha):
        """Manda uma linha ao fbw.py (CMD ..., APV ...). Sem o fbw.py, se perde."""
        if self._socket is None or self._endereco is None or not self._valido():
            return
        try:
            self._socket.sendto(linha.encode("ascii"), self._endereco)
        except OSError:
            pass

    def fechar(self):
        if self._socket is not None:
            self._socket.close()


class NaveKrpc:
    """Telemetria e comandos da nave ativa, pelo kRPC."""

    def __init__(self, conn, nave):
        self._conn = conn
        self._nave = nave
        self.corpo = nave.orbit.body
        self._raio = self.corpo.equatorial_radius
        superficie = nave.surface_reference_frame
        space_center = conn.space_center
        ReferenceFrame = space_center.ReferenceFrame

        # Referenciais "híbridos": posição e velocidade medidas em relação ao
        # planeta, mas escritas nos eixos do horizonte local da nave
        # (x = cima, y = norte, z = leste), que são os eixos da navball.
        # SUP: em relação ao chão, que gira com o planeta.
        # ORB: em relação ao centro do planeta, sem girar com ele. O alvo
        #      também é medido neste, e a diferença dá a velocidade relativa.
        ref_sup = ReferenceFrame.create_hybrid(
            position=self.corpo.reference_frame, rotation=superficie
        )
        self._ref_orb = ReferenceFrame.create_hybrid(
            position=self.corpo.non_rotating_reference_frame, rotation=superficie
        )

        voo = nave.flight(superficie)
        stream = conn.add_stream
        self._streams = {
            "pitch": stream(getattr, voo, "pitch"),
            "rumo": stream(getattr, voo, "heading"),
            "rolagem": stream(getattr, voo, "roll"),
            "altitude": stream(getattr, voo, "mean_altitude"),
            "radar": stream(getattr, voo, "surface_altitude"),
            "SUP": stream(getattr, nave.flight(ref_sup), "velocity"),
            "ORB": stream(getattr, nave.flight(self._ref_orb), "velocity"),
            "posicao": stream(nave.position, self._ref_orb),
            "apoastro": stream(getattr, nave.orbit, "apoapsis_altitude"),
            "periastro": stream(getattr, nave.orbit, "periapsis_altitude"),
            "tempo_apoastro": stream(getattr, nave.orbit, "time_to_apoapsis"),
            "tempo_periastro": stream(getattr, nave.orbit, "time_to_periapsis"),
            "excentricidade": stream(getattr, nave.orbit, "eccentricity"),
            "acelerador": stream(getattr, nave.control, "throttle"),
            "nos": stream(getattr, nave.control, "nodes"),
            # O alvo do jogo pode ser uma porta de acoplamento, uma nave ou um
            # planeta; só um deles fica diferente de None.
            "porta_alvo": stream(getattr, space_center, "target_docking_port"),
            "nave_alvo": stream(getattr, space_center, "target_vessel"),
            "corpo_alvo": stream(getattr, space_center, "target_body"),
        }
        for nome, propriedade in SISTEMAS.items():
            self._streams[nome] = stream(getattr, nave.control, propriedade)
        self._streams["sas_modo"] = stream(getattr, nave.control, "sas_mode")
        self._streams["ec"] = stream(nave.resources.amount, "ElectricCharge")
        self._streams["mp"] = stream(nave.resources.amount, "MonoPropellant")
        self._sas_mode = space_center.SASMode

        self._superficie = superficie
        self._alvo = None          # o alvo atual, como objeto do kRPC
        self._nome_alvo = None
        self._streams_alvo = {}    # posição e velocidade do alvo atual
        self._no = None            # o próximo nó de manobra
        self._stream_no = None     # a queima que falta nele

    def _acompanhar_alvo(self):
        """Se o alvo mudou no jogo, troca os streams de posição e velocidade."""
        s = self._streams
        candidatos = (
            ("porta", s["porta_alvo"]()),
            ("nave", s["nave_alvo"]()),
            ("corpo", s["corpo_alvo"]()),
        )
        tipo, alvo = next(((t, a) for t, a in candidatos if a is not None), (None, None))
        if alvo == self._alvo:
            return

        for antigo in self._streams_alvo.values():
            antigo.remove()
        self._streams_alvo = {}
        self._alvo = alvo
        if alvo is None:
            self._nome_alvo = None
            print("Alvo: nenhum")
            return

        # A porta de acoplamento não tem velocidade própria: usa a da peça.
        movel = alvo.part if tipo == "porta" else alvo
        self._nome_alvo = alvo.part.title if tipo == "porta" else alvo.name
        self._streams_alvo = {
            "posicao": self._conn.add_stream(alvo.position, self._ref_orb),
            "velocidade": self._conn.add_stream(movel.velocity, self._ref_orb),
        }
        print(f"Alvo: {self._nome_alvo}")

    def _acompanhar_manobra(self):
        """Se o próximo nó de manobra mudou, troca o stream da queima."""
        nos = self._streams["nos"]()
        no = nos[0] if nos else None
        if no == self._no:
            return
        if self._stream_no is not None:
            self._stream_no.remove()
            self._stream_no = None
        self._no = no
        if no is not None:
            # A queima que FALTA: durante a queima o marcador continua certo.
            self._stream_no = self._conn.add_stream(no.remaining_burn_vector, self._superficie)

    def ler(self):
        self._acompanhar_alvo()
        self._acompanhar_manobra()
        s = self._streams
        velocidades = {"SUP": s["SUP"](), "ORB": s["ORB"]()}
        nome_alvo = self._nome_alvo
        posicao_alvo = None
        if self._alvo is not None:
            try:
                posicao_alvo = tuple(
                    a - n for a, n in zip(self._streams_alvo["posicao"](), s["posicao"]())
                )
                velocidades["ALVO"] = tuple(
                    n - a for n, a in zip(velocidades["ORB"], self._streams_alvo["velocidade"]())
                )
            except (ValueError, RuntimeError):
                # O alvo acabou de sumir (ex.: destruído), e o jogo ainda não
                # avisou. Nesta volta, é como se não houvesse alvo.
                nome_alvo, posicao_alvo = None, None
                velocidades.pop("ALVO", None)
        manobra = None
        if self._stream_no is not None:
            try:
                manobra = self._stream_no()
            except (ValueError, RuntimeError):
                pass  # o nó acabou de ser apagado; a lista de nós avisa na próxima volta
        # Numa trajetória de escape (excentricidade >= 1) não há apoastro.
        escape = s["excentricidade"]() >= 1
        return Telemetria(
            pitch=s["pitch"](),
            rumo=s["rumo"](),
            rolagem=s["rolagem"](),
            velocidades=velocidades,
            altitude=s["altitude"](),
            radar=s["radar"](),
            raio_planeta=self._raio,
            posicao=s["posicao"](),
            apoastro=None if escape else s["apoastro"](),
            periastro=s["periastro"](),
            tempo_apoastro=None if escape else s["tempo_apoastro"](),
            tempo_periastro=s["tempo_periastro"](),
            acelerador=s["acelerador"](),
            alvo=nome_alvo,
            posicao_alvo=posicao_alvo,
            manobra=manobra,
            sistemas={nome: s[nome]() for nome in SISTEMAS},
            sas_modo=MODOS_DO_KRPC.get(s["sas_modo"]().name),
            sem_ec=s["ec"]() < RECURSO_MIN,
            sem_mp=s["mp"]() < RECURSO_MIN,
        )

    def escolher_modo(self, nome):
        """Korry de modo. Com o SAS desligado, liga junto. Se o jogo não
        aceitar o modo (sem alvo, sem nó, SAS fraco), nada muda: a luz
        continua no modo de antes."""
        try:
            if not self._streams["SAS"]():
                self._nave.control.sas = True
            self._nave.control.sas_mode = getattr(self._sas_mode, MODOS_KRPC[nome])
            print(f"SAS: modo {nome}")
        except (ValueError, RuntimeError) as e:
            print(f"O jogo não aceitou o modo {nome}: {e}")

    def alternar(self, nome):
        """O botão foi tocado: inverte o sistema. O botão só muda de cor
        quando o jogo confirmar, na próxima leitura."""
        ligar = not self._streams[nome]()
        try:
            setattr(self._nave.control, SISTEMAS[nome], ligar)
            print(f"{nome}: {'ligar' if ligar else 'desligar'}")
        except (ValueError, RuntimeError) as e:
            print(f"Não foi possível mudar {nome}: {e}")

    def remover(self):
        for s in (*self._streams.values(), *self._streams_alvo.values()):
            s.remove()
        if self._stream_no is not None:
            self._stream_no.remove()


class Demo:
    """Uma nave de mentira que se mexe sozinha, para testar a tela sem o KSP.

    Ela passa pelos 5 km do radar e pelos 33 e 36 km da troca SUP ⇄ ORB, a
    cada minuto ganha um alvo por 30 s e, a cada 90 s, um nó de manobra por 30 s.
    A cada 2 minutos, o ponto do fly by wire aparece por 40 s, andando em volta
    do pró-grado, como se um script estivesse mandando.
    """

    RAIO_KERBIN = 600_000  # m
    TERRENO = 700          # m: altura do chão sob a nave

    DEMORA_SAS = 4.0       # s: quanto a nave de mentira leva para chegar no marcador do modo
    ERRO_INICIAL = 35.0    # graus até o marcador quando o modo é escolhido

    def __init__(self):
        self._inicio = time.monotonic()
        self._sistemas = {nome: False for nome in SISTEMAS}
        self._progrado = (0.0, 0.0)   # (pitch, rumo) do movimento na última leitura
        self._sas_modo = "ESTAB"
        self._sas_desde = -math.inf   # quando o modo foi escolhido
        self.fbw = FbwDemo()

    def ler(self):
        t = time.monotonic() - self._inicio
        pitch = 20 + 40 * math.sin(t * 0.25)
        rumo = (90 + 12 * t) % 360
        rolagem = 30 * math.sin(t * 0.4)

        # O movimento segue o nariz com um pouco de atraso.
        p = math.radians(pitch - 8 + 5 * math.sin(t * 0.3))
        r = math.radians(rumo - 15)
        rapidez = 300 + 200 * math.sin(t * 0.1)
        sup = (
            rapidez * math.sin(p),
            rapidez * math.cos(p) * math.cos(r),
            rapidez * math.cos(p) * math.sin(r),
        )
        self._progrado = (math.degrees(p), math.degrees(r))
        # O chão de Kerbin anda ~175 m/s para leste no equador.
        velocidades = {"SUP": sup, "ORB": (sup[0], sup[1], sup[2] + 175)}

        alvo = posicao_alvo = None
        if t % 60 >= 30:
            alvo = "ESTACAO"
            distancia = 1500 + 1000 * math.sin(t * 0.2)
            direcao = (math.radians(10), math.radians(rumo + 40))
            posicao_alvo = (
                distancia * math.sin(direcao[0]),
                distancia * math.cos(direcao[0]) * math.cos(direcao[1]),
                distancia * math.cos(direcao[0]) * math.sin(direcao[1]),
            )
            velocidades["ALVO"] = (1.5, 4 * math.sin(t * 0.3), -6.0)

        manobra = None
        if t % 90 >= 60:
            manobra = (30.0, 20.0 * math.cos(t * 0.1), 80.0 * (90 - t % 90) / 30)

        altitude = 30_000 + 25_000 * math.sin(t * 0.05)
        return Telemetria(
            pitch=pitch,
            rumo=rumo,
            rolagem=rolagem,
            velocidades=velocidades,
            altitude=altitude,
            radar=altitude - self.TERRENO,
            raio_planeta=self.RAIO_KERBIN,
            posicao=(self.RAIO_KERBIN + altitude, 0.0, 0.0),
            apoastro=80_000 + 20_000 * math.sin(t * 0.07),
            periastro=-250_000 + 200_000 * math.sin(t * 0.07),
            tempo_apoastro=1_700 - (t * 10) % 1_700,
            tempo_periastro=3_400 - (t * 10) % 3_400,
            acelerador=0.5 + 0.5 * math.sin(t * 0.15),
            alvo=alvo,
            posicao_alvo=posicao_alvo,
            manobra=manobra,
            sistemas=dict(self._sistemas),
            sas_modo=self._sas_modo,
            sem_mp=t % 120 >= 100,   # o monopropelente "acaba" por 20 s a cada 2 min
            erro_sas=self._erro_sas(alvo is not None, manobra is not None),
        )

    def _erro_sas(self, tem_alvo, tem_no):
        """A nave de mentira chega no marcador em DEMORA_SAS segundos."""
        if self._sas_modo == "ESTAB":
            return None
        if self._sas_modo in ("ALVO", "AALVO") and not tem_alvo or self._sas_modo == "MAN" and not tem_no:
            return None
        passou = time.monotonic() - self._sas_desde
        return max(0.0, self.ERRO_INICIAL * (1 - passou / self.DEMORA_SAS))

    def escolher_modo(self, nome):
        t = time.monotonic() - self._inicio
        if nome in ("ALVO", "AALVO") and t % 60 < 30 or nome == "MAN" and t % 90 < 60:
            print(f"SAS: o jogo não aceitaria {nome} agora (sem alvo ou sem nó)")
            return
        self._sistemas["SAS"] = True
        if nome != self._sas_modo:
            self._sas_modo, self._sas_desde = nome, time.monotonic()
        print(f"SAS: modo {nome}")

    def ponto_fbw(self):
        """Faz o papel dos scripts (Scripts.ponto_fbw) na demonstração."""
        t = time.monotonic() - self._inicio
        if t % 120 >= 40:
            return None
        pitch, rumo = self._progrado
        return (pitch + 6 * math.sin(t * 0.7), (rumo + 12 * math.cos(t * 0.4)) % 360)

    def alternar(self, nome):
        self._sistemas[nome] = not self._sistemas[nome]
        print(f"{nome}: {'ligar' if self._sistemas[nome] else 'desligar'}")

    def estado_fbw(self):
        return self.fbw.estado()

    def comando_fbw(self, linha):
        self.fbw.executar(linha)

    def remover(self):
        pass


class FbwDemo:
    """Faz o papel do scripts/fbw.py na demonstração: um avião voando no FBW.

    Os modos ligam e desligam com os comandos do painel, e o ALT fica armado
    por uns segundos antes de chegar na altitude. A cada 2 minutos, por 8 s,
    o avião fica devagar demais: o alpha floor liga (ESTOL), e os modos desligam.
    """

    ALT_DEMORA = 6.0   # s até o ALT armado "chegar"
    ESTOL_A_CADA = 120.0
    ESTOL_DURA = 8.0

    def __init__(self):
        self._inicio = time.monotonic()
        self.ligado = True
        self.modos = dict.fromkeys(("HDG", "ALT", "VS"), False)
        self._alt_desde = None
        self.trava = None

    def executar(self, linha):
        partes = linha.split()
        if partes[:1] != ["CMD"]:
            return   # os valores (APV) não mudam nada na demonstração
        nome = partes[1]
        if nome == "FBW":
            self.ligado = not self.ligado
            if not self.ligado:
                self.modos = dict.fromkeys(self.modos, False)
                self.trava = None
        elif nome == "TRAVA" and self.ligado:
            self.trava = None if self.trava is not None else 12_000
            if self.trava is not None:
                self.modos["ALT"] = self.modos["VS"] = False
        elif nome in self.modos and self.ligado:
            self.modos[nome] = not self.modos[nome]
            if nome == "ALT" and self.modos["ALT"]:
                self._alt_desde = time.monotonic()
            if nome in ("ALT", "VS") and self.modos[nome]:
                self.trava = None
        print(f"FBW (demonstração): {linha}")

    def estado(self):
        t = time.monotonic() - self._inicio
        estol = self.ligado and self.ESTOL_A_CADA - self.ESTOL_DURA <= t % self.ESTOL_A_CADA
        if estol:
            self.modos = dict.fromkeys(self.modos, False)   # o piloto automático desliga
        alt = 0
        if self.modos["ALT"]:
            alt = 1 if time.monotonic() - self._alt_desde > self.ALT_DEMORA else 2
            if alt == 1:
                self.modos["VS"] = False   # chegou: o V/S termina
        return {
            "LEI": f"LEI {'FBW' if self.ligado else 'DIRETA'}",
            "TRAVA": f"TRAVA {self.trava if self.trava is not None else 'OFF'}",
            "ESTOL": f"ESTOL {int(estol)}",
            "APL HDG": f"APL HDG {int(self.modos['HDG'])}",
            "APL ALT": f"APL ALT {alt}",
            "APL VS": f"APL VS {int(self.modos['VS'])}",
        }


def tratar_mensagem(linha, fonte, transmissor, modo):
    """Executa uma mensagem que veio da tela. Devolve True se a tela reiniciou."""
    if linha == "READY":
        print("A tela (re)iniciou.")
        transmissor.esquecer()
        return True

    tipo, _, nome = linha.partition(" ")
    if tipo == "TOQUE" and nome == "MODO":
        modo.alternar()
    elif tipo == "TOQUE" and nome in SISTEMAS:
        fonte.alternar(nome)
    elif tipo == "ERR":
        print(f"A tela não entendeu a mensagem: {nome}")
    else:
        print(f"Mensagem desconhecida da tela: {linha}")
    return False


class Acoes:
    """O que o painel de sistemas pede: ao jogo (fonte) ou ao fbw.py (scripts)."""

    def __init__(self, fonte, scripts):
        self.alternar = fonte.alternar
        self.escolher_modo = fonte.escolher_modo
        self.comando_fbw = scripts.comando_fbw


def voar(tela, transmissor, fonte, scripts, continua_valida, painel=None, sistemas=None):
    """Mantém a tela atualizada até continua_valida() dizer que não.

    painel: a página de botões do painel de sistemas (ou, um dia, o painel
    de verdade), que manda BTN e ENC e recebe as luzes; pode faltar.
    sistemas: a lógica do painel, que continua de uma nave para a outra.
    """
    modo = ModoNavball()
    sistemas = sistemas or Sistemas(None)
    sistemas.acoes = Acoes(fonte, scripts)
    luzes_painel = Remetente(painel.enviar) if painel is not None else None
    luzes_tela = Remetente(tela.enviar)
    proxima_verificacao = proximas_luzes = 0.0
    while True:
        agora = time.monotonic()
        t = fonte.ler()

        anterior = modo.modo
        for linha in tela.linhas():
            if tratar_mensagem(linha, fonte, transmissor, modo):
                luzes_tela.esquecer()
        if painel is not None:
            for linha in painel.linhas():
                if linha == "READY":
                    luzes_painel.esquecer()
                elif not sistemas.tratar(linha, agora, t.rumo, t.altitude):
                    print(f"Linha desconhecida do painel: {linha[:40]}")
        sistemas.atualizar(agora)
        atual = modo.atualizar(t)
        if atual != anterior:
            print(f"Modo da navball: {atual}")

        transmissor.enviar(t, atual, agora, scripts.ponto_fbw())
        if agora >= proximas_luzes:
            proximas_luzes = agora + INTERVALO_LUZES
            erro = erro_do_sas(t, atual) if t.sas_modo is not None else None
            sas, rcs = t.sistemas["SAS"], t.sistemas["RCS"]
            luzes = sistemas.luzes(sas, rcs, t.sas_modo, erro, t.sem_ec, t.sem_mp, scripts.estado_fbw())
            luzes_tela.mandar(sistemas.tela(luzes, erro, sas), agora)
            if luzes_painel is not None:
                luzes_painel.mandar(luzes, agora)

        if agora >= proxima_verificacao:
            if not continua_valida():
                return
            proxima_verificacao = agora + VERIFICA_NAVE

        time.sleep(0.01)


def acompanhar_nave(conn, tela, transmissor, scripts, nave, painel, sistemas):
    """Acompanha uma nave até ela deixar de ser a ativa ou trocar de planeta.

    Ao trocar de planeta (ex.: entrar na esfera de influência da Mun), os
    referenciais da velocidade precisam ser refeitos com o planeta novo.
    """
    fonte = NaveKrpc(conn, nave)
    print(f"Nave: {nave.name} ({fonte.corpo.name})")
    transmissor.esquecer()
    try:
        voar(
            tela,
            transmissor,
            fonte,
            scripts,
            lambda: conn.space_center.active_vessel == nave and nave.orbit.body == fonte.corpo,
            painel,
            sistemas,
        )
    finally:
        fonte.remover()


def abrir_tela(args):
    if args.celular:
        from mfd_celular import TelaCelular
        try:
            return TelaCelular(args.celular)
        except OSError as e:
            sys.exit(f"Não foi possível abrir a porta {args.celular} para o celular: {e}")

    if not args.porta:
        # Só o simulador precisa do pygame; importar aqui evita exigir o
        # pygame de quem usa a placa de verdade.
        from mfd_simulador import Simulador
        return Simulador(zoom=args.zoom)

    print(f"Abrindo a tela em {args.porta}...")
    try:
        tela = Painel(args.porta)   # a tela fala o mesmo tipo de linhas que o painel
    except serial.SerialException as e:
        sys.exit(f"Não foi possível abrir {args.porta}: {e}")
    if tela.esperar_ready():
        print("Tela pronta.")
    else:
        print("A tela não mandou READY; seguindo assim mesmo.")
    return tela


def abrir_painel(args):
    """A página de botões do painel de sistemas, no navegador do celular ou do PC."""
    if args.sem_painel:
        return None
    from mfd_celular import TelaCelular, PAGINA_PAINEL
    try:
        return TelaCelular(args.painel, PAGINA_PAINEL, "a página de botões do painel de sistemas")
    except OSError as e:
        sys.exit(f"Não foi possível abrir a porta {args.painel} para o painel: {e}")


def main():
    parser = argparse.ArgumentParser(description="Ponte kRPC ⇄ tela multifunção.")
    parser.add_argument(
        "address",
        nargs="?",
        default="127.0.0.1",
        help="IP do computador onde o KSP está rodando (padrão: este computador)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="não conecta no KSP: uma nave de mentira se mexe sozinha",
    )
    telas = parser.add_mutually_exclusive_group()
    telas.add_argument(
        "--porta",
        help="porta serial da mikromedia, ex.: COM7 (padrão: simulador numa janela)",
    )
    telas.add_argument(
        "--celular",
        nargs="?",
        type=int,
        const=8000,
        metavar="PORTA",
        help="mostra a tela no navegador do celular; PORTA de rede, padrão 8000",
    )
    painel = parser.add_mutually_exclusive_group()
    painel.add_argument(
        "--painel",
        type=int,
        default=PORTA_PAINEL,
        metavar="PORTA",
        help=f"porta de rede da página de botões do painel de sistemas (padrão: {PORTA_PAINEL})",
    )
    painel.add_argument("--sem-painel", action="store_true", help="não abre a página de botões do painel")
    parser.add_argument(
        "--zoom",
        type=int,
        default=2,
        choices=range(1, 5),
        help="quantas vezes ampliar a janela do simulador (padrão: 2)",
    )
    args = parser.parse_args()

    # O kRPC primeiro: enquanto o connect espera alguém aceitar a conexão no
    # jogo, a janela do simulador ficaria congelada.
    conn = None if args.demo else conectar_krpc(args.address)
    tela = abrir_tela(args)
    painel = abrir_painel(args)
    transmissor = Transmissor(tela)
    sistemas = Sistemas(None)
    scripts = None
    try:
        if args.demo:
            print("Demonstração: a nave se mexe sozinha. Clique nos botões da tela e do painel.")
            demo = Demo()
            voar(tela, transmissor, demo, demo, lambda: True, painel, sistemas)
        else:
            scripts = Scripts()
            while True:
                nave = esperar_nave(conn, tela)
                try:
                    acompanhar_nave(conn, tela, transmissor, scripts, nave, painel, sistemas)
                except (ValueError, RuntimeError):
                    # A nave deixou de existir ou o jogo saiu da cena de voo.
                    pass
    except KeyboardInterrupt:
        print()
    except serial.SerialException:
        print("\nA tela foi desconectada.")
    finally:
        tela.fechar()
        if painel is not None:
            painel.fechar()
        if scripts is not None:
            scripts.fechar()
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
