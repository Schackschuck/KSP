"""Painel de scripts: os korry POUSO e LANCAR e os lugares dos próximos scripts.

O painel (hardware/construcao.md#painel-de-scripts) só manda o aperto e a
soltura do korry (BTN POUSO 1 e BTN POUSO 0, BTN LANCAR 1 e BTN LANCAR 0); o
tempo é medido aqui, como no encoder do piloto automático:

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

O LANCAR abre o scripts/subida.py com os valores do menu da subida (MenuSubida),
que um encoder à parte mexe (ENC SUB e BTN SUB): altitude, inclinação e se a
órbita vai no plano do alvo. O menu aparece na página SUBIDA da tela, que só a
mikromedia desenha. Cada script tem a sua página na tela (PAGINAS).
"""

import math
import os
import signal
import subprocess
import sys
import threading
import time

from sistemas import RAPIDO, VEZES_RAPIDO

SCRIPTS = ("POUSO", "LANCAR")   # os korry que já têm script; os outros lugares do painel estão vagos
PAGINAS = {"POUSO": "POUSO", "LANCAR": "SUBIDA"}
LINHAS_SUBIDA = ("ALT", "INC", "PLANO")
VALORES_SUBIDA = {"ALT": 80, "INC": 0, "PLANO": 0}
LIMITES_SUBIDA = {"ALT": (10, 5000), "INC": (0, 180)}
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

    argumentos: a lista de argumentos depois do "python", ou uma função que
    devolve essa lista, chamada em cada iniciar() (para os valores que mudam
    entre uma abertura e outra, como o menu da subida).
    """

    def __init__(self, nome, argumentos):
        self.nome = nome
        self._argumentos = argumentos   # depois de "python", ex.: ["scripts/pouso.py", "--demo"]
        self._processo = None
        self._abortar_em = None

    def iniciar(self):
        argumentos = self._argumentos() if callable(self._argumentos) else self._argumentos
        opcoes = {}
        if sys.platform == "win32":
            # Um grupo próprio: o Ctrl+C do terminal da ponte não chega nele, e
            # o CTRL_BREAK da ponte chega só nele.
            opcoes["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            opcoes["start_new_session"] = True
        ambiente = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self._processo = subprocess.Popen(
            [sys.executable] + argumentos,
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
        print(f"[{self.nome.lower()}] aberto: {' '.join(argumentos)}")

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


class MenuSubida:
    """O menu da página SUBIDA da tela, mexido por um encoder só.

    Três linhas: ALT (a altitude da órbita, em km), INC (a inclinação, em
    graus) e PLANO (a órbita no plano do alvo, 0 ou 1). Girar move o cursor
    entre as linhas; apertar escolhe a linha, e girar muda o valor; apertar de
    novo sai. Os valores valem para a próxima vez que o LANCAR abrir o script.
    """

    def __init__(self):
        self.cursor = 0
        self.editando = False
        self.valores = dict(VALORES_SUBIDA)
        self._apertado_em = None
        self._ultimo_giro = -math.inf

    @property
    def linha(self):
        return LINHAS_SUBIDA[self.cursor]

    def girar(self, cliques, agora):
        rapido = abs(cliques) > 1 or agora - self._ultimo_giro < RAPIDO
        self._ultimo_giro = agora
        if not self.editando:
            self.cursor = max(0, min(len(LINHAS_SUBIDA) - 1, self.cursor + cliques))
            return
        nome = self.linha
        if nome == "PLANO":
            if cliques != 0:
                self.valores[nome] = 1 - self.valores[nome]
            return
        minimo, maximo = LIMITES_SUBIDA[nome]
        valor = self.valores[nome] + cliques * (VEZES_RAPIDO if rapido else 1)
        self.valores[nome] = max(minimo, min(maximo, valor))

    def apertar(self, agora):
        self._apertado_em = agora

    def soltar(self):
        if self._apertado_em is not None:
            self.editando = not self.editando
        self._apertado_em = None

    def sair(self):
        self.editando = False
        self._apertado_em = None

    def linhas(self):
        """As linhas SBV e SBC, que vão só para a tela."""
        estado = {f"SBV {nome}": f"SBV {nome} {valor}" for nome, valor in self.valores.items()}
        estado["SBC"] = f"SBC {self.linha} {int(self.editando)}"
        return estado

    def argumentos(self):
        """Os argumentos do scripts/subida.py com os valores de agora."""
        argumentos = ["--altitude", str(self.valores["ALT"] * 1000), "--inclinacao", str(self.valores["INC"])]
        if self.valores["PLANO"]:
            argumentos.append("--plano-do-alvo")
        return argumentos


def processo_subida(endereco_ksp, menu, demo=False, tela="127.0.0.1"):
    """O scripts/subida.py, com os valores do menu na hora de abrir (tela: IP ou IP:PORTA)."""
    script = os.path.normpath(os.path.join(PASTA_SCRIPTS, "subida.py"))

    def argumentos():
        return [script, "--tela", tela] + menu.argumentos() + (["--demo"] if demo else [endereco_ksp])

    return Processo("LANCAR", argumentos)


class PainelScripts:
    """O painel de scripts, entre o painel, a tela e os processos dos scripts.

    processos: nome do korry → objeto com iniciar(), abortar(), rodando() e
    codigo (ver Processo).
    menu: o MenuSubida mexido pelo encoder da subida (ENC SUB e BTN SUB), ou
    None sem ele.
    """

    def __init__(self, processos, menu=None):
        self.processos = processos
        self.menu = menu
        self._apertado = {}       # nome → quando o korry foi apertado (só enquanto está apertado)
        self._abortado = set()    # scripts que o piloto mandou abortar
        self._rodando = set()     # scripts que estavam rodando na última atualização
        self._fim = {}            # nome → (estado final, até quando mostrar)

    def tratar(self, linha, agora, pagina="NAV"):
        """Executa uma linha do painel.

        Devolve None se ela não é deste painel; senão a página que a tela deve
        abrir, ou "" para nenhuma. pagina é a que a tela mostra agora: com ela
        fora da SUBIDA, o primeiro toque no encoder da subida só abre a página.
        """
        partes = linha.split()
        if len(partes) != 3:
            return None
        tipo, nome, valor = partes
        if tipo == "BTN" and nome in self.processos and valor in ("0", "1"):
            if valor == "1":
                self._apertado.setdefault(nome, agora)
                return PAGINAS.get(nome, "")
            self._apertado.pop(nome, None)
            return ""
        if self.menu is not None and nome == "SUB" and tipo in ("ENC", "BTN"):
            return self._encoder(tipo, valor, agora, pagina)
        return None

    def _encoder(self, tipo, valor, agora, pagina):
        if tipo == "ENC":
            try:
                cliques = int(valor)
            except ValueError:
                return None
        elif valor not in ("0", "1"):
            return None
        if pagina == "SUBIDA":
            if tipo == "ENC":
                self.menu.girar(cliques, agora)
            elif valor == "1":
                self.menu.apertar(agora)
            else:
                self.menu.soltar()
        return PAGINAS["LANCAR"]

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

    def pagina_em_uso(self, agora):
        """A página da tela do script em uso (ver em_uso), ou None."""
        return PAGINAS.get(self.em_uso(agora))

    def sair_do_menu(self):
        """A tela saiu da página SUBIDA: o menu volta a mover o cursor."""
        if self.menu is not None:
            self.menu.sair()

    def tela(self):
        """As linhas só para a tela: o menu da subida (SBV e SBC)."""
        return self.menu.linhas() if self.menu is not None else {}

    def luzes(self, agora):
        """As linhas SCR, que vão para o painel e para a tela."""
        return {f"SCR {nome}": f"SCR {nome} {self.estado(nome, agora)}" for nome in self.processos}

    def fechar(self):
        for processo in self.processos.values():
            processo.fechar()
