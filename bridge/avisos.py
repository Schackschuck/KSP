"""Avisos de voo por voz, como o GPWS dos aviões de linha, e a luz do painel.

A ponte da tela (mfd.py) chama Avisos.atualizar() a cada leitura do jogo, em
qualquer nave voando na atmosfera, com ou sem o fbw.py. Os avisos:

- PULL UP e TERRAIN (vermelho): descendo rápido demais para a altura
  (SINK RATE que piorou) ou o chão chegando rápido (TERRAIN, e PULL UP se
  continuar).
- SINK RATE, DON'T SINK, TOO LOW GEAR, TOO LOW TERRAIN, BANK ANGLE e
  OVERSPEED (âmbar).
- As chamadas de altura no pouso (100, 50, 40, 30, 20, 10 pés), com o trem
  baixado e descendo.

A Voz fala a frase: pela gravação em bridge/sons/<nome>.wav, se existir, ou
pelo espeak-ng (no Pi: sudo apt install espeak-ng). Sem nenhum dos dois, só
escreve no terminal. Limites e roteiro de testes em docs/avisos.md.
"""

import math
import os
import queue
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass

PES = 0.3048

PRESSAO_MIN = 500.0
RADAR_GPWS = 750.0

SINK_BASE, SINK_POR_METRO = 4.9, 0.0277
PULL_UP_BASE, PULL_UP_POR_METRO = 8.6, 0.0417

TERRENO_MAX = 500.0
TERRENO_BASE, TERRENO_POR_METRO = 10.0, 0.075
TAU_APROXIMACAO = 1.0
TERRENO_PULL_UP_DEPOIS = 1.6

DECOLAGEM_ATE = 300.0
PERDA_MIN, PERDA_FRACAO = 10.0, 0.1

TOO_LOW = 150.0
TOO_LOW_VELOCIDADE = 100.0

INCLINACAO_ALTA = 300.0
INCLINACAO_BASE, INCLINACAO_TOPO, INCLINACAO_ALTURA = 10.0, 45.0, 40.0
INCLINACAO_REARMA = 5.0

PRESSAO_OVERSPEED = 50_000.0

CHAMADAS = (100, 50, 40, 30, 20, 10)
CHAMADAS_REARMA = 200

INTERVALO_ENTRE_FALAS = 1.0

FRASES = {
    "PULL_UP": "pull up",
    "TERRAIN": "terrain, terrain",
    "SINK_RATE": "sink rate",
    "DONT_SINK": "don't sink",
    "TOO_LOW_GEAR": "too low, gear",
    "TOO_LOW_TERRAIN": "too low, terrain",
    "BANK_ANGLE": "bank angle, bank angle",
    "OVERSPEED": "overspeed",
    100: "one hundred",
    50: "fifty",
    40: "forty",
    30: "thirty",
    20: "twenty",
    10: "ten",
}

AVISOS = (
    ("PULL_UP", 2, 1.2),
    ("TERRAIN", 2, 2.5),
    ("TOO_LOW_TERRAIN", 1, 3.0),
    ("TOO_LOW_GEAR", 1, 3.0),
    ("SINK_RATE", 1, 2.0),
    ("DONT_SINK", 1, 2.0),
    ("BANK_ANGLE", 1, 3.0),
    ("OVERSPEED", 1, 3.0),
)


@dataclass
class Voo:
    """O que os avisos precisam saber do avião.

    radar em m acima do chão (ou do mar); vv em m/s, positiva subindo;
    velocidade em m/s em relação ao chão; rolagem em graus; pressao, a
    dinâmica, em Pa; trem: True baixado, False recolhido, None sem trem.
    """
    radar: float
    vv: float
    velocidade: float
    rolagem: float
    pressao: float
    no_ar: bool
    trem: bool = None


class Avisos:
    """Decide qual aviso falar e a cor da luz, a cada leitura."""

    def __init__(self):
        self.ativos = set()
        self.nivel = 0
        self._falado_em = {}
        self._ultima_fala = -math.inf
        self._anterior = None
        self._aproximacao = 0.0
        self._terreno_desde = None
        self._decolagem = None
        self._viu_o_chao = False
        self._chamadas_armadas = set(CHAMADAS)
        self._inclinacao_armada = True

    def atualizar(self, v, agora):
        """Devolve o nome da frase a falar agora (uma chave de FRASES), ou None."""
        if not v.no_ar:
            self._viu_o_chao = True
        voando = v.no_ar and v.pressao >= PRESSAO_MIN
        if not voando:
            self._esquecer()
            return None
        dt = 0.0 if self._anterior is None else agora - self._anterior[0]
        if dt > 0.0:
            aproximacao = -(v.radar - self._anterior[1]) / dt
            self._aproximacao += (aproximacao - self._aproximacao) * min(1.0, dt / TAU_APROXIMACAO)
        self._anterior = (agora, v.radar)
        if self._viu_o_chao:
            self._decolagem = v.radar
            self._viu_o_chao = False

        self.ativos = self._condicoes(v, agora)
        self.nivel = max((nivel for nome, nivel, _ in AVISOS if nome in self.ativos), default=0)
        fala = self._escolher_fala(agora)
        if fala is None and not self.ativos:
            fala = self._chamada(v)
        if fala is not None:
            self._ultima_fala = agora
            self._falado_em[fala] = agora
        return fala

    def _esquecer(self):
        self.ativos = set()
        self.nivel = 0
        self._anterior = None
        self._aproximacao = 0.0
        self._terreno_desde = None
        self._decolagem = None
        self._chamadas_armadas = set(CHAMADAS)

    def _condicoes(self, v, agora):
        ativos = set()
        h = v.radar
        desce = -v.vv
        if h < RADAR_GPWS:
            if desce > PULL_UP_BASE + PULL_UP_POR_METRO * h:
                ativos.add("PULL_UP")
            elif desce > SINK_BASE + SINK_POR_METRO * h:
                ativos.add("SINK_RATE")

        terreno = (
            h < TERRENO_MAX and v.trem is not True
            and self._aproximacao > TERRENO_BASE + TERRENO_POR_METRO * h
        )
        if terreno:
            if self._terreno_desde is None:
                self._terreno_desde = agora
            ativos.add("PULL_UP" if agora - self._terreno_desde >= TERRENO_PULL_UP_DEPOIS else "TERRAIN")
        else:
            self._terreno_desde = None

        if self._decolagem is not None:
            self._decolagem = max(self._decolagem, h)
            if self._decolagem > DECOLAGEM_ATE:
                self._decolagem = None
            elif v.vv < 0 and self._decolagem - h > max(PERDA_MIN, PERDA_FRACAO * self._decolagem):
                ativos.add("DONT_SINK")

        if v.trem is False and self._decolagem is None and h < TOO_LOW:
            ativos.add("TOO_LOW_GEAR" if v.velocidade < TOO_LOW_VELOCIDADE else "TOO_LOW_TERRAIN")

        if h < INCLINACAO_ALTA:
            limite = INCLINACAO_BASE + (INCLINACAO_TOPO - INCLINACAO_BASE) * min(1.0, h / INCLINACAO_ALTURA)
            if abs(v.rolagem) > limite:
                if self._inclinacao_armada:
                    ativos.add("BANK_ANGLE")
            elif abs(v.rolagem) < limite - INCLINACAO_REARMA:
                self._inclinacao_armada = True

        if v.pressao > PRESSAO_OVERSPEED:
            ativos.add("OVERSPEED")
        return ativos

    def _escolher_fala(self, agora):
        if agora - self._ultima_fala < INTERVALO_ENTRE_FALAS:
            return None
        for nome, _, intervalo in AVISOS:
            if nome in self.ativos:
                if agora - self._falado_em.get(nome, -math.inf) >= intervalo:
                    if nome == "BANK_ANGLE":
                        self._inclinacao_armada = False
                    return nome
                return None
        return None

    def _chamada(self, v):
        pes = v.radar / PES
        if pes > CHAMADAS_REARMA:
            self._chamadas_armadas = set(CHAMADAS)
            return None
        if v.trem is not True or v.vv >= 0:
            return None
        cruzadas = [c for c in self._chamadas_armadas if pes <= c]
        if not cruzadas:
            return None
        self._chamadas_armadas -= set(cruzadas)
        return min(cruzadas)


class Voz:
    """Fala as frases numa thread, sem travar a ponte. A mais nova substitui a que ainda não começou."""

    PASTA_SONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sons")

    def __init__(self, dispositivo=None, ligada=True):
        self._dispositivo = dispositivo
        self._ligada = ligada
        self._espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        self._aplay = shutil.which("aplay")
        self._fila = queue.Queue(maxsize=1)
        if ligada:
            if self._espeak is None:
                print("Avisos: sem o espeak-ng, a voz só aparece no terminal (no Pi: sudo apt install espeak-ng).")
            threading.Thread(target=self._falar_sempre, daemon=True).start()

    def falar(self, nome):
        print(f"[AVISO] {FRASES[nome].upper()}")
        if not self._ligada:
            return
        try:
            self._fila.get_nowait()
        except queue.Empty:
            pass
        self._fila.put_nowait(nome)

    def _falar_sempre(self):
        while True:
            nome = self._fila.get()
            try:
                self._tocar(nome)
            except OSError as e:
                print(f"Avisos: não consegui tocar a voz: {e}")

    def _tocar(self, nome):
        gravacao = os.path.join(self.PASTA_SONS, f"{str(nome).lower()}.wav")
        if os.path.exists(gravacao):
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(gravacao, winsound.SND_FILENAME)
            elif self._aplay:
                subprocess.run(self._aplay_comando() + [gravacao], check=False)
            return
        if self._espeak is None:
            return
        fala = [self._espeak, "-v", "en-us", "-s", "170", FRASES[nome]]
        if self._dispositivo and self._aplay:
            espeak = subprocess.Popen(fala + ["--stdout"], stdout=subprocess.PIPE)
            subprocess.run(self._aplay_comando(), stdin=espeak.stdout, check=False)
            espeak.stdout.close()
            espeak.wait()
        else:
            subprocess.run(fala, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _aplay_comando(self):
        comando = [self._aplay, "-q"]
        if self._dispositivo:
            comando += ["-D", self._dispositivo]
        return comando
