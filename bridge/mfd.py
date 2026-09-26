"""Ponte kRPC ⇄ tela multifunção: navball, telemetria e botões de toque.

A tela (a mikromedia for ARM, 320x240 com touch) só desenha o que recebe;
toda a conta que envolve o jogo fica aqui. Enquanto o firmware da placa não
existe, a tela é um simulador numa janela do PC (mfd_simulador.py), que fala o
mesmo protocolo. Protocolo em docs/protocolo.md; roteiro em docs/mfd.md.

Uso:
    python mfd.py                    # KSP neste computador, tela simulada
    python mfd.py --demo             # sem o KSP: a nave se mexe sozinha
    python mfd.py 192.168.1.10       # KSP em outro computador
    python mfd.py --zoom 3           # janela do simulador maior
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
INTERVALO_NUMEROS = 0.1   # s: altitude e velocidade; também servem de "estou vivo"
INTERVALO_ORBITA = 0.5    # s: apoastro e periastro mudam devagar
REENVIO_ESTADOS = 1.0     # s: reenvia os estados mesmo sem mudança, por segurança
VERIFICA_NAVE = 1.0       # s: de quanto em quanto tempo conferir se a nave ou o planeta mudou
VEL_MIN_MARCADOR = 0.5    # m/s: abaixo disso a direção do movimento é só ruído
INT32_MAX = 2**31 - 1     # a placa guarda os números em inteiros de 32 bits

# Sinal da rolagem que o kRPC informa. Se, ao rolar a nave para a direita
# (tecla E), a navball da tela girar ao contrário da navball do jogo, troque
# para -1.
SINAL_ROLAGEM = 1

# Botões de toque que ligam e desligam sistemas: nome no protocolo →
# propriedade de vessel.control no kRPC. O botão MODO é tratado à parte.
SISTEMAS = {
    "SAS": "sas",
    "RCS": "rcs",
}


@dataclass
class Telemetria:
    pitch: float        # graus acima do horizonte
    rumo: float         # graus: 0 = norte, 90 = leste
    rolagem: float      # graus
    velocidade: tuple   # (cima, norte, leste) em m/s, no modo da navball
    altitude: float     # m acima do nível do mar
    apoastro: float     # m; None numa trajetória de escape
    periastro: float    # m
    sistemas: dict      # {"SAS": True, "RCS": False}


def inteiro32(valor):
    return max(-INT32_MAX, min(INT32_MAX, round(valor)))


def decimos(graus):
    """Ângulos vão em décimos de grau, como inteiros: 45,3° vira 453."""
    return inteiro32(graus * 10)


def distancia(metros):
    if metros is None or not math.isfinite(metros):
        return "OFF"
    return str(inteiro32(metros))


def mensagem_progrado(velocidade):
    """PRO com a direção do movimento, ou PRO OFF se a nave está parada."""
    cima, norte, leste = velocidade
    modulo = math.sqrt(cima**2 + norte**2 + leste**2)
    if modulo < VEL_MIN_MARCADOR:
        return "PRO OFF"
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, cima / modulo))))
    rumo = math.degrees(math.atan2(leste, norte))
    return f"PRO {decimos(pitch)} {decimos(rumo) % 3600}"


class Transmissor:
    """Decide o que mandar para a tela e quando."""

    def __init__(self, tela):
        self.tela = tela
        self.modo = "SUP"   # modo da navball: SUP (superfície) ou ORB (órbita)
        self.esquecer()

    def esquecer(self):
        """A tela reiniciou ou a nave mudou: tudo vai de novo na próxima volta."""
        self._enviados = {}
        self._proximo = {"atitude": 0.0, "numeros": 0.0, "orbita": 0.0, "estados": 0.0}

    def _chegou_a_vez(self, tarefa, intervalo, agora):
        if agora < self._proximo[tarefa]:
            return False
        self._proximo[tarefa] = agora + intervalo
        return True

    def enviar(self, t, agora):
        enviar = self.tela.enviar
        if self._chegou_a_vez("atitude", INTERVALO_ATITUDE, agora):
            enviar(f"ATT {decimos(t.pitch)} {decimos(t.rumo) % 3600} {decimos(t.rolagem)}")
            enviar(mensagem_progrado(t.velocidade))

        if self._chegou_a_vez("numeros", INTERVALO_NUMEROS, agora):
            enviar(f"ALT {inteiro32(t.altitude)}")
            modulo = math.sqrt(sum(v**2 for v in t.velocidade))
            enviar(f"VEL {inteiro32(modulo * 10)}")   # décimos de m/s

        if self._chegou_a_vez("orbita", INTERVALO_ORBITA, agora):
            enviar(f"AP {distancia(t.apoastro)}")
            enviar(f"PE {distancia(t.periastro)}")

        # Estados: cada um vai quando muda (resposta rápida no botão) e todos
        # vão a cada REENVIO_ESTADOS, caso alguma mensagem tenha se perdido.
        reenviar = self._chegou_a_vez("estados", REENVIO_ESTADOS, agora)
        estados = {nome: str(int(ligado)) for nome, ligado in t.sistemas.items()}
        estados["MODO"] = self.modo
        for nome, valor in estados.items():
            if reenviar or self._enviados.get(nome) != valor:
                enviar(f"{nome} {valor}")
                self._enviados[nome] = valor


class NaveKrpc:
    """Telemetria e comandos da nave ativa, pelo kRPC."""

    def __init__(self, conn, nave):
        self._nave = nave
        self.corpo = nave.orbit.body
        superficie = nave.surface_reference_frame
        ReferenceFrame = conn.space_center.ReferenceFrame

        # Referenciais "híbridos": a velocidade é medida em relação ao
        # planeta, mas escrita nos eixos do horizonte local da nave
        # (x = cima, y = norte, z = leste), que são os eixos da navball.
        # SUP: em relação ao chão, que gira com o planeta.
        # ORB: em relação ao centro do planeta, sem girar com ele.
        ref_sup = ReferenceFrame.create_hybrid(
            position=self.corpo.reference_frame, rotation=superficie
        )
        ref_orb = ReferenceFrame.create_hybrid(
            position=self.corpo.non_rotating_reference_frame, rotation=superficie
        )

        voo = nave.flight(superficie)
        stream = conn.add_stream
        self._streams = {
            "pitch": stream(getattr, voo, "pitch"),
            "rumo": stream(getattr, voo, "heading"),
            "rolagem": stream(getattr, voo, "roll"),
            "altitude": stream(getattr, voo, "mean_altitude"),
            "SUP": stream(getattr, nave.flight(ref_sup), "velocity"),
            "ORB": stream(getattr, nave.flight(ref_orb), "velocity"),
            "apoastro": stream(getattr, nave.orbit, "apoapsis_altitude"),
            "periastro": stream(getattr, nave.orbit, "periapsis_altitude"),
            "excentricidade": stream(getattr, nave.orbit, "eccentricity"),
        }
        for nome, propriedade in SISTEMAS.items():
            self._streams[nome] = stream(getattr, nave.control, propriedade)

    def ler(self, modo):
        s = self._streams
        # Numa trajetória de escape (excentricidade >= 1) não há apoastro.
        escape = s["excentricidade"]() >= 1
        return Telemetria(
            pitch=s["pitch"](),
            rumo=s["rumo"](),
            rolagem=SINAL_ROLAGEM * s["rolagem"](),
            velocidade=s[modo](),
            altitude=s["altitude"](),
            apoastro=None if escape else s["apoastro"](),
            periastro=s["periastro"](),
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
        for s in self._streams.values():
            s.remove()


class Demo:
    """Uma nave de mentira que se mexe sozinha, para testar a tela sem o KSP."""

    def __init__(self):
        self._inicio = time.monotonic()
        self._sistemas = {nome: False for nome in SISTEMAS}

    def ler(self, modo):
        t = time.monotonic() - self._inicio
        pitch = 20 + 40 * math.sin(t * 0.25)
        rumo = (90 + 12 * t) % 360
        rolagem = 30 * math.sin(t * 0.4)

        # O movimento segue o nariz com um pouco de atraso.
        p = math.radians(pitch - 8 + 5 * math.sin(t * 0.3))
        r = math.radians(rumo - 15)
        rapidez = 300 + 200 * math.sin(t * 0.1)
        cima = rapidez * math.sin(p)
        norte = rapidez * math.cos(p) * math.cos(r)
        leste = rapidez * math.cos(p) * math.sin(r)
        if modo == "ORB":
            leste += 175  # o chão de Kerbin anda ~175 m/s para leste no equador

        return Telemetria(
            pitch=pitch,
            rumo=rumo,
            rolagem=rolagem,
            velocidade=(cima, norte, leste),
            altitude=30_000 + 25_000 * math.sin(t * 0.05),
            apoastro=80_000 + 20_000 * math.sin(t * 0.07),
            periastro=-250_000 + 200_000 * math.sin(t * 0.07),
            sistemas=dict(self._sistemas),
        )

    def alternar(self, nome):
        self._sistemas[nome] = not self._sistemas[nome]
        print(f"{nome}: {'ligar' if self._sistemas[nome] else 'desligar'}")

    def remover(self):
        pass


def tratar_mensagem(linha, fonte, transmissor):
    """Executa uma mensagem que veio da tela."""
    if linha == "READY":
        print("A tela (re)iniciou.")
        transmissor.esquecer()
        return

    tipo, _, nome = linha.partition(" ")
    if tipo == "TOQUE" and nome == "MODO":
        # O modo é só da tela: muda a velocidade e o pró-grado mostrados.
        transmissor.modo = "ORB" if transmissor.modo == "SUP" else "SUP"
        print(f"Modo da navball: {transmissor.modo}")
    elif tipo == "TOQUE" and nome in SISTEMAS:
        fonte.alternar(nome)
    elif tipo == "ERR":
        print(f"A tela não entendeu a mensagem: {nome}")
    else:
        print(f"Mensagem desconhecida da tela: {linha}")


def voar(tela, transmissor, fonte, continua_valida):
    """Mantém a tela atualizada até continua_valida() dizer que não."""
    proxima_verificacao = 0.0
    while True:
        agora = time.monotonic()

        for linha in tela.linhas():
            tratar_mensagem(linha, fonte, transmissor)

        transmissor.enviar(fonte.ler(transmissor.modo), agora)

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
    parser.add_argument(
        "--porta",
        help="porta serial da mikromedia, ex.: COM7 (padrão: simulador numa janela)",
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
