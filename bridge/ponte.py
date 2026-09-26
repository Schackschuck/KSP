"""Ponte kRPC ⇄ painel (fase 1, protocolo v0 em texto).

Liga o jogo ao painel: o que o painel manda (botões) vira comando no KSP, e o
estado do KSP (SAS, altitude) vira mensagem para o painel. O painel não sabe
que o KSP existe; toda a "inteligência" fica aqui.

Uso:
    python ponte.py                                 # KSP neste computador, painel detectado sozinho
    python ponte.py 192.168.1.10                    # KSP em outro computador (ex.: rodando no Pi)
    python ponte.py --porta COM5                    # escolhe a porta serial na mão
    python ponte.py --porta /dev/ttyACM0 192.168.1.10
"""

import argparse
import sys
import time

import krpc
import serial
from serial.tools import list_ports

BAUD = 115200             # precisa ser igual ao Serial.begin() do firmware
INTERVALO_ALT = 0.1       # s: altitude 10x por segundo; o painel acusa "sem sinal" após 1 s quieto
REENVIO_SAS = 1.0         # s: reenvia o SAS mesmo sem mudança, por segurança
VERIFICA_NAVE = 1.0       # s: de quanto em quanto tempo conferir se a nave ativa mudou
ESPERA_READY = 4.0        # s: tempo máximo esperando o painel terminar de ligar
ALT_MAX = 2**31 - 1       # o painel guarda a altitude num long de 32 bits

# Identificadores USB (VID) dos chips USB-serial mais comuns em placas Arduino.
VIDS_ARDUINO = {
    0x2341,  # Arduino (Mega original)
    0x2A03,  # Arduino.org
    0x1A86,  # CH340 (clones)
}


class Painel:
    """Conversa com o firmware do painel pela serial, uma mensagem por linha."""

    def __init__(self, porta):
        # timeout=0: read() devolve na hora o que já chegou, sem esperar.
        # Assim o laço principal nunca trava esperando o painel.
        self._serial = serial.Serial(porta, BAUD, timeout=0)
        self._buffer = b""

    def linhas(self):
        """Devolve as linhas completas que chegaram desde a última chamada.

        A serial entrega bytes soltos, não mensagens: uma linha pode chegar
        pela metade e se completar na chamada seguinte. O pedaço incompleto
        fica guardado em self._buffer até o '\\n' chegar.
        """
        self._buffer += self._serial.read(self._serial.in_waiting or 1)
        *completas, self._buffer = self._buffer.split(b"\n")
        if len(self._buffer) > 1000:  # lixo sem '\n' (ex.: baud errado): descarta
            self._buffer = b""
        linhas = [l.decode("ascii", errors="replace").strip() for l in completas]
        return [l for l in linhas if l]

    def enviar(self, mensagem):
        self._serial.write(mensagem.encode("ascii") + b"\n")

    def esperar_ready(self):
        """Espera o painel mandar READY. Devolve False se não vier a tempo.

        Abrir a porta serial reinicia o Mega (é assim que a Arduino IDE grava
        o firmware sem você apertar o reset). O bootloader leva ~2 s, e o que
        for enviado nesse tempo se perde.
        """
        limite = time.monotonic() + ESPERA_READY
        while time.monotonic() < limite:
            if "READY" in self.linhas():
                return True
            time.sleep(0.01)
        return False

    def fechar(self):
        self._serial.close()


def encontrar_porta():
    """Procura a porta serial do painel pelo fabricante do chip USB."""
    portas = list(list_ports.comports())
    candidatas = [p.device for p in portas if p.vid in VIDS_ARDUINO]
    if len(candidatas) == 1:
        return candidatas[0]

    motivo = "Nenhum Arduino encontrado." if not candidatas else "Mais de um Arduino encontrado."
    lista = "\n".join(f"  {p.device}  ({p.description})" for p in portas) or "  (nenhuma)"
    sys.exit(f"{motivo} Escolha a porta com --porta. Portas seriais disponíveis:\n{lista}")


def conectar_krpc(address):
    # Se o auto-accept estiver desligado, o connect fica parado até alguém
    # aceitar a conexão na janela do kRPC, dentro do jogo.
    print(f"Conectando ao kRPC em {address}... (se demorar, aceite a conexão no jogo)")
    try:
        return krpc.connect(name="KSP Cockpit", address=address)
    except krpc.ConnectionError as e:
        sys.exit(f"O servidor kRPC recusou a conexão: {e}")
    except ConnectionRefusedError:
        sys.exit(
            f"{address} recusou a conexão. O servidor kRPC está iniciado, "
            "com o endereço em 'Any'?"
        )
    except OSError as e:
        sys.exit(
            f"Não foi possível alcançar {address} ({e}). Confira o IP, o firewall "
            "e se a rede do Windows está como Privada."
        )


def esperar_nave(conn, painel):
    """Espera existir uma nave ativa (cena de voo) e a devolve."""
    avisou = False
    while True:
        try:
            return conn.space_center.active_vessel
        except (ValueError, RuntimeError):
            # Fora da cena de voo (KSC, hangar, menu) não há nave ativa.
            if not avisou:
                print("Nenhuma nave ativa. Aguardando a cena de voo...")
                avisou = True

        # Enquanto espera, lê e DESCARTA o que o painel mandar: um STAGE
        # apertado no hangar não pode ficar guardado e disparar sozinho quando
        # o foguete chegar na plataforma.
        fim = time.monotonic() + 1.0
        while time.monotonic() < fim:
            painel.linhas()
            time.sleep(0.02)


def ativar_estagio(nave):
    try:
        nave.control.activate_next_stage()
        print("STAGE!")
    except (ValueError, RuntimeError) as e:
        # Ex.: os estágios estão travados no jogo (staging lock).
        print(f"Não foi possível ativar o estágio: {e}")


def voar(conn, painel, nave):
    """Mantém painel e nave sincronizados até a nave deixar de ser a ativa."""
    print(f"Nave: {nave.name}")

    # Streams: o servidor manda os valores novos sozinho, e ler sas() ou
    # altitude() só pega o último valor recebido, sem ir até o PC.
    sas = conn.add_stream(getattr, nave.control, "sas")
    altitude = conn.add_stream(getattr, nave.flight(), "mean_altitude")

    ultimo_sas = None           # None = o painel ainda não sabe o SAS
    proximo_alt = 0.0           # instantes (time.monotonic) das próximas tarefas
    proximo_reenvio_sas = 0.0
    proxima_verificacao = 0.0

    try:
        while True:
            agora = time.monotonic()

            # 1. Painel → jogo.
            for linha in painel.linhas():
                if linha == "BTN STAGE 1":
                    ativar_estagio(nave)
                elif linha == "READY":
                    # O painel reiniciou (ex.: cabo mexido) e esqueceu tudo.
                    # Zerar ultimo_sas força o reenvio logo abaixo.
                    print("O painel reiniciou.")
                    ultimo_sas = None
                elif linha.startswith("ERR "):
                    print(f"O painel não entendeu a mensagem: {linha[4:]}")
                # "BTN STAGE 0" (botão solto) não faz nada por enquanto.

            # 2. Jogo → painel. O SAS vai quando muda (resposta rápida no LED)
            # e também a cada REENVIO_SAS, caso alguma mensagem tenha se perdido.
            estado_sas = sas()
            if estado_sas != ultimo_sas or agora >= proximo_reenvio_sas:
                painel.enviar(f"SAS {int(estado_sas)}")
                ultimo_sas = estado_sas
                proximo_reenvio_sas = agora + REENVIO_SAS

            # A altitude vai sempre, mesmo parada: ela também serve de
            # "estou vivo" para o painel, que acusa sem sinal após 1 s quieto.
            if agora >= proximo_alt:
                metros = max(-ALT_MAX, min(ALT_MAX, round(altitude())))
                painel.enviar(f"ALT {metros}")
                proximo_alt = agora + INTERVALO_ALT

            # 3. A nave ativa ainda é esta? Ela muda ao trocar de nave com as
            # teclas [ e ], ao voltar para o KSC e lançar outra etc.
            if agora >= proxima_verificacao:
                if conn.space_center.active_vessel != nave:
                    return
                proxima_verificacao = agora + VERIFICA_NAVE

            # Uma pausa curta para não ocupar 100% da CPU à toa. 10 ms é bem
            # menos que o tempo de um aperto de botão.
            time.sleep(0.01)
    except (ValueError, RuntimeError):
        # Um stream ou chamada deu erro: a nave deixou de existir ou o jogo
        # saiu da cena de voo. Quem chamou volta a esperar uma nave.
        return
    finally:
        sas.remove()
        altitude.remove()


def main():
    parser = argparse.ArgumentParser(description="Ponte kRPC ⇄ painel (protocolo v0).")
    parser.add_argument(
        "address",
        nargs="?",
        default="127.0.0.1",
        help="IP do computador onde o KSP está rodando (padrão: este computador)",
    )
    parser.add_argument(
        "--porta",
        help="porta serial do painel, ex.: COM5 ou /dev/ttyACM0 (padrão: detectar)",
    )
    args = parser.parse_args()

    porta = args.porta or encontrar_porta()
    print(f"Abrindo o painel em {porta}...")
    try:
        painel = Painel(porta)
    except serial.SerialException as e:
        sys.exit(
            f"Não foi possível abrir {porta}: {e}\n"
            "Confira o nome da porta (na Arduino IDE: Ferramentas → Porta) e se o "
            "Serial Monitor está fechado: só um programa pode usar a porta."
        )
    if painel.esperar_ready():
        print("Painel pronto.")
    else:
        print("O painel não mandou READY; seguindo assim mesmo.")

    conn = conectar_krpc(args.address)
    try:
        while True:
            nave = esperar_nave(conn, painel)
            voar(conn, painel, nave)
    except KeyboardInterrupt:
        print()
    except serial.SerialException:
        print("\nO painel foi desconectado.")
    finally:
        conn.close()
        painel.fechar()


if __name__ == "__main__":
    main()
