"""Painel de scripts: o korry POUSO e os lugares dos próximos scripts.

O painel (hardware/construcao.md#painel-de-scripts) só manda o aperto e a
soltura do korry (BTN POUSO 1 e BTN POUSO 0); o tempo é medido aqui, como no
encoder do piloto automático:

- segurar SEGURAR segundos com o script parado abre o script;
- segurar SEGURAR segundos com ele voando aborta: o script corta o motor e
  devolve a nave ao piloto;
- soltar antes não faz nada.

Um script ativo por vez. O script roda num processo próprio (Processo), e
continua sendo o mesmo que roda sozinho pela linha de comando. O estado vai
para o painel e para a tela na linha SCR (docs/protocolo.md#painel-de-scripts),
e o korry mostra o que o script está fazendo, não o aperto:

  OFF      apagado: parado
  LIGA <s> âmbar piscando: segurando para abrir, com os segundos que faltam
  ATIVO    verde: o script está voando
  DESL <s> verde e âmbar piscando: segurando para abortar
  FIM      apagado: terminou bem (a nave pousou); a tela mostra por MOSTRA_FIM
  ABORT    vermelho por MOSTRA_FIM: abortado pelo piloto
  FALHA    vermelho por MOSTRA_FIM: o script parou sem terminar (erro, nave perdida)
"""

import math
import os
import signal
import subprocess
import sys
import threading
import time

SCRIPTS = ("POUSO",)   # os korry que já têm script; os outros lugares do painel estão vagos
SEGURAR = 5.0          # s com o korry apertado para abrir ou abortar o script
MOSTRA_FIM = 10.0      # s que o fim (FIM, ABORT, FALHA) fica no korry e na tela
ESPERA_ABORTAR = 5.0   # s: o script que não sai depois do pedido de abortar é encerrado à força

PASTA_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
POUSOU = 0             # código de saída do scripts/pouso.py quando a nave pousou


class Processo:
    """Um script de voo (scripts/) rodando num processo próprio.

    O que o script escreve aparece no terminal da ponte, com o nome dele na
    frente. Abortar manda o mesmo Ctrl+C do terminal (no Windows, o
    CTRL_BREAK, que o script transforma em Ctrl+C): o script corta o motor e
    devolve a nave ao piloto antes de sair.
    """

    def __init__(self, nome, argumentos):
        self.nome = nome
        self._argumentos = argumentos   # depois de "python", ex.: ["scripts/pouso.py", "--demo"]
        self._processo = None
        self._abortar_em = None

    def iniciar(self):
        opcoes = {}
        if sys.platform == "win32":
            # Um grupo próprio: o Ctrl+C do terminal da ponte não chega nele, e
            # o CTRL_BREAK da ponte chega só nele.
            opcoes["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            opcoes["start_new_session"] = True
        ambiente = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self._processo = subprocess.Popen(
            [sys.executable] + self._argumentos,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            env=ambiente,
            **opcoes,
        )
        self._abortar_em = None
        threading.Thread(target=self._repetir_saida, args=(self._processo,), daemon=True).start()
        print(f"[{self.nome.lower()}] aberto: {' '.join(self._argumentos)}")

    def _repetir_saida(self, processo):
        with processo.stdout:
            for linha in processo.stdout:
                if linha.strip():
                    print(f"[{self.nome.lower()}] {linha.rstrip()}")

    def abortar(self):
        if self._processo is None or self._processo.poll() is not None:
            return
        self._abortar_em = time.monotonic()
        try:
            if sys.platform == "win32":
                self._processo.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._processo.send_signal(signal.SIGINT)
        except OSError:
            pass

    def rodando(self):
        """True enquanto o processo existe. Quem não sai depois de abortar é encerrado."""
        if self._processo is None:
            return False
        if self._processo.poll() is not None:
            return False
        if self._abortar_em is not None and time.monotonic() - self._abortar_em > ESPERA_ABORTAR:
            print(f"[{self.nome.lower()}] não saiu depois de abortar: encerrado à força")
            self._processo.kill()
        return True

    @property
    def codigo(self):
        """O código de saída, ou None se nunca rodou ou ainda está rodando."""
        return None if self._processo is None else self._processo.poll()

    def fechar(self):
        """A ponte está saindo: aborta o script e espera ele sair."""
        if self._processo is None or self._processo.poll() is not None:
            return
        self.abortar()
        try:
            self._processo.wait(ESPERA_ABORTAR)
        except subprocess.TimeoutExpired:
            self._processo.kill()


def processo_pouso(endereco_ksp, demo=False, tela="127.0.0.1"):
    """O scripts/pouso.py, mandando o estado para esta ponte (tela: IP ou IP:PORTA)."""
    script = os.path.normpath(os.path.join(PASTA_SCRIPTS, "pouso.py"))
    argumentos = [script, "--tela", tela]
    argumentos += ["--demo"] if demo else [endereco_ksp]
    return Processo("POUSO", argumentos)


class PainelScripts:
    """O painel de scripts, entre o painel, a tela e os processos dos scripts.

    processos: nome do korry → objeto com iniciar(), abortar(), rodando() e
    codigo (ver Processo).
    """

    def __init__(self, processos):
        self.processos = processos
        self._apertado = {}       # nome → quando o korry foi apertado (só enquanto está apertado)
        self._abortado = set()    # scripts que o piloto mandou abortar
        self._rodando = set()     # scripts que estavam rodando na última atualização
        self._fim = {}            # nome → (estado final, até quando mostrar)

    def tratar(self, linha, agora):
        """Executa uma linha do painel. Devolve False se ela não é deste painel."""
        partes = linha.split()
        if len(partes) != 3 or partes[0] != "BTN" or partes[1] not in self.processos or partes[2] not in ("0", "1"):
            return False
        nome = partes[1]
        if partes[2] == "1":
            self._apertado.setdefault(nome, agora)
        else:
            self._apertado.pop(nome, None)
        return True

    def ativo(self):
        """O nome do script voando, ou None."""
        return next(iter(self._rodando), None)

    def atualizar(self, agora):
        """Chamar a cada volta: o aperto longo e o fim dos processos."""
        for nome, processo in self.processos.items():
            rodando = processo.rodando()
            if nome in self._rodando and not rodando:
                self._rodando.discard(nome)
                if nome in self._abortado:
                    final = "ABORT"
                elif processo.codigo == POUSOU:
                    final = "FIM"
                else:
                    final = "FALHA"
                self._abortado.discard(nome)
                self._fim[nome] = (final, agora + MOSTRA_FIM)
                print(f"Script {nome}: {final} (código {processo.codigo})")

        for nome, desde in list(self._apertado.items()):
            if desde is None or agora - desde < SEGURAR:
                continue
            self._apertado[nome] = None   # uma vez por aperto: só vale de novo depois de soltar
            if nome in self._rodando:
                print(f"Script {nome}: abortar")
                self._abortado.add(nome)
                self.processos[nome].abortar()
            elif self.ativo() is not None:
                print(f"Script {nome}: {self.ativo()} ainda está voando; um script por vez")
            else:
                self._fim.pop(nome, None)
                try:
                    self.processos[nome].iniciar()
                except OSError as e:
                    print(f"Script {nome}: não abriu ({e})")
                    self._fim[nome] = ("FALHA", agora + MOSTRA_FIM)
                    continue
                self._rodando.add(nome)

    def estado(self, nome, agora):
        """O estado do korry, como vai na linha SCR (sem o 'SCR <nome>')."""
        desde = self._apertado.get(nome)
        if desde is not None:
            faltam = max(1, math.ceil(SEGURAR - (agora - desde)))
            return f"{'DESL' if nome in self._rodando else 'LIGA'} {faltam}"
        if nome in self._rodando:
            return "ATIVO"
        final, ate = self._fim.get(nome, (None, 0.0))
        if final is not None and agora < ate:
            return final
        return "OFF"

    def em_uso(self, agora):
        """O script da página da tela: um korry apertado, um script voando ou um fim recente."""
        for nome in self.processos:
            if self.estado(nome, agora) != "OFF":
                return nome
        return None

    def luzes(self, agora):
        """As linhas SCR, que vão para o painel e para a tela."""
        return {f"SCR {nome}": f"SCR {nome} {self.estado(nome, agora)}" for nome in self.processos}

    def fechar(self):
        for processo in self.processos.values():
            processo.fechar()
