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
"""

import argparse
import math
import sys
import time
from dataclasses import dataclass

import serial

from ponte import Painel, conectar_krpc, esperar_nave

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


def mensagem_direcao(nome, vetor, minimo):
    """<nome> <pitch> <rumo> com a direção do vetor (cima, norte, leste),
    ou <nome> OFF se o vetor for curto demais para ter direção."""
    tamanho = modulo(vetor)
    if tamanho < minimo:
        return f"{nome} OFF"
    cima, norte, leste = vetor
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, cima / tamanho))))
    rumo = math.degrees(math.atan2(leste, norte))
    return f"{nome} {decimos(pitch)} {decimos(rumo) % 3600}"


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

    def enviar(self, t, modo, agora):
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
        )

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
    """

    RAIO_KERBIN = 600_000  # m
    TERRENO = 700          # m: altura do chão sob a nave

    def __init__(self):
        self._inicio = time.monotonic()
        self._sistemas = {nome: False for nome in SISTEMAS}

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
        )

    def alternar(self, nome):
        self._sistemas[nome] = not self._sistemas[nome]
        print(f"{nome}: {'ligar' if self._sistemas[nome] else 'desligar'}")

    def remover(self):
        pass


def tratar_mensagem(linha, fonte, transmissor, modo):
    """Executa uma mensagem que veio da tela."""
    if linha == "READY":
        print("A tela (re)iniciou.")
        transmissor.esquecer()
        return

    tipo, _, nome = linha.partition(" ")
    if tipo == "TOQUE" and nome == "MODO":
        modo.alternar()
    elif tipo == "TOQUE" and nome in SISTEMAS:
        fonte.alternar(nome)
    elif tipo == "ERR":
        print(f"A tela não entendeu a mensagem: {nome}")
    else:
        print(f"Mensagem desconhecida da tela: {linha}")


def voar(tela, transmissor, fonte, continua_valida):
    """Mantém a tela atualizada até continua_valida() dizer que não."""
    modo = ModoNavball()
    proxima_verificacao = 0.0
    while True:
        agora = time.monotonic()
        t = fonte.ler()

        anterior = modo.modo
        for linha in tela.linhas():
            tratar_mensagem(linha, fonte, transmissor, modo)
        atual = modo.atualizar(t)
        if atual != anterior:
            print(f"Modo da navball: {atual}")

        transmissor.enviar(t, atual, agora)

        if agora >= proxima_verificacao:
            if not continua_valida():
                return
            proxima_verificacao = agora + VERIFICA_NAVE

        time.sleep(0.01)


def acompanhar_nave(conn, tela, transmissor, nave):
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
            lambda: conn.space_center.active_vessel == nave and nave.orbit.body == fonte.corpo,
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
    transmissor = Transmissor(tela)
    try:
        if args.demo:
            print("Demonstração: a nave se mexe sozinha. Clique nos botões da tela.")
            voar(tela, transmissor, Demo(), lambda: True)
        else:
            while True:
                nave = esperar_nave(conn, tela)
                try:
                    acompanhar_nave(conn, tela, transmissor, nave)
                except (ValueError, RuntimeError):
                    # A nave deixou de existir ou o jogo saiu da cena de voo.
                    pass
    except KeyboardInterrupt:
        print()
    except serial.SerialException:
        print("\nA tela foi desconectada.")
    finally:
        tela.fechar()
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
