"""Fase 0: imprime ao vivo a altitude da nave ativa, lida do kRPC pela rede.

Uso:
    python fase0_altitude.py                # KSP rodando neste computador
    python fase0_altitude.py 192.168.1.10   # KSP rodando em outro computador (ex.: a partir do Pi)
"""

import argparse
import sys
import time

import krpc


def connect(address):
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


def wait_for_vessel(conn):
    # Fora da cena de voo (KSC, hangar, menu) não existe nave ativa e o kRPC
    # responde com erro. Em vez de encerrar, espera o jogador lançar uma nave.
    warned = False
    while True:
        try:
            return conn.space_center.active_vessel
        except (ValueError, RuntimeError):
            if not warned:
                print("Nenhuma nave ativa. Aguardando a cena de voo...")
                warned = True
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "address",
        nargs="?",
        default="127.0.0.1",
        help="IP do computador onde o KSP está rodando (padrão: este computador)",
    )
    args = parser.parse_args()

    conn = connect(args.address)
    try:
        while True:
            vessel = wait_for_vessel(conn)
            print(f"Conectado! Nave: {vessel.name}  (Ctrl+C para sair)")
            altitude = conn.add_stream(getattr, vessel.flight(), "mean_altitude")
            try:
                while True:
                    text = f"{altitude():>12,.0f} m".replace(",", ".")
                    print(f"\r{text}", end="", flush=True)
                    time.sleep(0.1)
            except (ValueError, RuntimeError):
                # O stream passou a devolver erro (a nave deixou de existir,
                # o voo foi revertido...): volta a esperar uma nave.
                print()
                altitude.remove()
    except KeyboardInterrupt:
        print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
