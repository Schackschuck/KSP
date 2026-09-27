"""Painel de sistemas de controle: modos do SAS, SAS, RCS, FBW e piloto automático.

A lógica do painel (hardware/construcao.md#painel-de-sistemas-de-controle)
fica aqui, sem o kRPC: quem chama (bridge/mfd.py) lê o jogo e executa os
pedidos. O painel só manda botões e cliques, e a ponte decide:

- korry de modo (BTN SAS_<modo>): escolhe o modo do SAS no jogo;
- korry SAS e RCS: inverte o sistema; FBW e TRAVA: vão para o fbw.py;
- encoder (ENC AP, BTN AP): o menu da página do piloto automático, na tela;
- a página da tela: SAS ao mexer no SAS, AP ao mexer no encoder, e a navball
  de novo PAGINA_DURA segundos depois do último toque.

As luzes voltam nas mesmas linhas para o painel e para a tela. Protocolo em
docs/protocolo.md#painel-de-sistemas-de-controle.
"""

import math

MODOS_SAS = ("ESTAB", "MAN", "PRO", "RETRO", "NRM", "ANRM", "RFORA", "RDENTRO", "ALVO", "AALVO")
LINHAS_AP = ("HDG", "ALT", "VS")   # as linhas do menu, de cima para baixo

PAGINA_DURA = 10.0     # s depois do último toque no painel até a tela voltar para a navball
SEGURAR = 1.0          # s com o encoder apertado para ligar ou desligar o modo
RAPIDO = 0.08          # s: cliques mais juntos que isso contam como girar rápido
VEZES_RAPIDO = 10      # girando rápido, o valor anda 10 vezes mais
VERDE_ENTRA = 2.0      # graus: o modo do SAS fica verde com a nave mais perto que isso do marcador...
VERDE_SAI = 4.0        # ...e volta para azul mais longe que isso (a folga evita piscar)
REENVIO = 1.0          # s: as luzes vão de novo mesmo sem mudar, caso uma linha se perca

# Por clique, girando devagar: 1°, 10 m e 0,1 m/s (a V/S vai em décimos).
PASSO = {"HDG": 1, "ALT": 10, "VS": 1}
LIMITES = {"ALT": (0, 99_990), "VS": (-500, 500)}   # m e décimos de m/s; o HDG dá a volta


class MenuPiloto:
    """O menu da página do piloto automático, mexido por um encoder só.

    Girar move o cursor entre as linhas; apertar escolhe a linha, e girar
    muda o valor; apertar de novo sai. Segurar SEGURAR segundos liga ou
    desliga o modo da linha, na hora, sem esperar soltar.
    """

    def __init__(self):
        self.cursor = 0
        self.editando = False
        self.valores = None            # {"HDG": graus, "ALT": m, "VS": décimos de m/s}
        self._apertado_em = None
        self._segurou = False
        self._ultimo_giro = -math.inf

    @property
    def linha(self):
        return LINHAS_AP[self.cursor]

    def iniciar(self, rumo, altitude):
        """Na primeira vez, os valores começam onde o avião está."""
        if self.valores is None:
            self.valores = {"HDG": round(rumo) % 360, "ALT": max(0, round(altitude / 10) * 10), "VS": 0}

    def girar(self, cliques, agora):
        rapido = abs(cliques) > 1 or agora - self._ultimo_giro < RAPIDO
        self._ultimo_giro = agora
        if not self.editando:
            self.cursor = max(0, min(len(LINHAS_AP) - 1, self.cursor + cliques))
            return
        nome = self.linha
        valor = self.valores[nome] + cliques * PASSO[nome] * (VEZES_RAPIDO if rapido else 1)
        if nome == "HDG":
            valor %= 360
        else:
            minimo, maximo = LIMITES[nome]
            valor = max(minimo, min(maximo, valor))
        self.valores[nome] = valor

    def apertar(self, agora):
        self._apertado_em = agora
        self._segurou = False

    def soltar(self):
        if self._apertado_em is not None and not self._segurou:
            self.editando = not self.editando
        self._apertado_em = None

    def segurou(self, agora):
        """O nome do modo a ligar ou desligar, uma vez por aperto longo; senão None."""
        if self._apertado_em is None or self._segurou or agora - self._apertado_em < SEGURAR:
            return None
        self._segurou = True
        return self.linha

    def sair(self):
        self.editando = False
        self._apertado_em = None

    def linhas(self):
        if self.valores is None:
            return {}
        estado = {f"APV {nome}": f"APV {nome} {valor}" for nome, valor in self.valores.items()}
        estado["APC"] = f"APC {self.linha} {int(self.editando)}"
        return estado


class CorDoModo:
    """Azul enquanto a nave vira para o marcador, verde quando chegou."""

    def __init__(self):
        self._modo = None
        self._verde = False

    def atualizar(self, modo, erro):
        """erro: graus entre o nariz e o marcador; None quando não dá para medir."""
        if modo != self._modo:
            self._modo, self._verde = modo, False
        if modo == "ESTAB":
            self._verde = True            # segura a atitude de agora: já chegou
        elif erro is None:
            self._verde = False
        elif erro < VERDE_ENTRA:
            self._verde = True
        elif erro > VERDE_SAI:
            self._verde = False
        return "V" if self._verde else "A"


class Remetente:
    """Manda as linhas quando mudam e também a cada REENVIO segundos."""

    def __init__(self, enviar):
        self._enviar = enviar
        self._enviados = {}
        self._proximo = 0.0

    def esquecer(self):
        self._enviados = {}
        self._proximo = 0.0

    def mandar(self, estado, agora):
        """estado: chave → linha. A chave diz qual linha substitui qual."""
        todas = agora >= self._proximo
        if todas:
            self._proximo = agora + REENVIO
        for chave, linha in estado.items():
            if todas or self._enviados.get(chave) != linha:
                self._enviar(linha)
                self._enviados[chave] = linha


class Sistemas:
    """O painel de sistemas de controle, entre o painel, a tela, o jogo e o fbw.py.

    acoes: quem executa os pedidos no jogo e no fbw.py, com
      alternar(nome)       inverte SAS ou RCS no jogo
      escolher_modo(nome)  escolhe o modo do SAS no jogo
      comando_fbw(linha)   manda uma linha ao fbw.py (CMD ..., APV ...)
    """

    def __init__(self, acoes):
        self.acoes = acoes
        self.menu = MenuPiloto()
        self.pagina = "NAV"
        self._fecha_em = 0.0
        self._cor = CorDoModo()
        self._apv_enviados = {}
        self._proximo_apv = 0.0

    def _abrir(self, pagina, agora):
        if pagina != self.pagina:
            self.menu.sair()
        self.pagina = pagina
        self._fecha_em = agora + PAGINA_DURA

    def tratar(self, linha, agora, rumo, altitude):
        """Executa uma linha do painel. Devolve False se ela não é deste painel."""
        partes = linha.split()
        if len(partes) == 3 and partes[0] == "BTN":
            nome, apertou = partes[1], partes[2] == "1"
            if nome.startswith("SAS_") and nome[4:] in MODOS_SAS:
                if apertou:
                    self._abrir("SAS", agora)
                    self.acoes.escolher_modo(nome[4:])
                return True
            if nome in ("SAS", "RCS"):
                if apertou:
                    self._abrir("SAS", agora)
                    self.acoes.alternar(nome)
                return True
            if nome in ("FBW", "TRAVA"):
                if apertou:
                    self.acoes.comando_fbw(f"CMD {nome}")
                return True
            if nome == "AP":
                self._encoder(apertou, None, agora, rumo, altitude)
                return True
        if len(partes) == 3 and partes[0] == "ENC" and partes[1] == "AP":
            try:
                cliques = int(partes[2])
            except ValueError:
                return False
            self._encoder(None, cliques, agora, rumo, altitude)
            return True
        return False

    def _encoder(self, apertou, cliques, agora, rumo, altitude):
        """Com a tela noutra página, o primeiro toque só abre a página do piloto."""
        aberta = self.pagina == "AP"
        self._abrir("AP", agora)
        self.menu.iniciar(rumo, altitude)
        if not aberta:
            return
        if cliques is not None:
            self.menu.girar(cliques, agora)
        elif apertou:
            self.menu.apertar(agora)
        else:
            self.menu.soltar()

    def atualizar(self, agora):
        """Chamar a cada volta: o aperto longo do encoder, a volta à navball e os valores para o fbw.py."""
        nome = self.menu.segurou(agora)
        if nome is not None:
            self._fecha_em = agora + PAGINA_DURA
            self.acoes.comando_fbw(f"CMD {nome}")
        if self.pagina != "NAV" and agora >= self._fecha_em:
            self.pagina = "NAV"
            self.menu.sair()
        # Os valores do menu vão ao fbw.py quando mudam e a cada REENVIO.
        valores = self.menu.valores or {}
        todos = agora >= self._proximo_apv
        if todos:
            self._proximo_apv = agora + REENVIO
        for nome, valor in valores.items():
            if todos or self._apv_enviados.get(nome) != valor:
                self.acoes.comando_fbw(f"APV {nome} {valor}")
                self._apv_enviados[nome] = valor

    def luzes(self, sas, rcs, sas_modo, erro, sem_ec, sem_mp, fbw):
        """As linhas das luzes, que vão para o painel e para a tela.

        sas_modo: o modo do SAS no jogo (um de MODOS_SAS), ou None.
        erro: graus entre o nariz e o marcador do modo, ou None.
        fbw: as linhas de estado do fbw.py (LEI, TRAVA, APL ...), já com OFF se ele não está aberto.
        """
        if sas and sas_modo is not None:
            cor = self._cor.atualizar(sas_modo, erro)
            sasm = f"SASM {sas_modo} {cor}"
        else:
            self._cor.atualizar(None, None)
            sasm = "SASM OFF"
        estado = {
            "SAS": f"SAS {int(sas)}",
            "RCS": f"RCS {int(rcs)}",
            "SASM": sasm,
            "SEMEC": f"SEMEC {int(sas and sem_ec)}",
            "SEMMP": f"SEMMP {int(rcs and sem_mp)}",
        }
        estado.update(fbw)
        return estado

    def tela(self, luzes, erro, sas):
        """O que vai só para a tela: a página, o erro e o menu, além das luzes."""
        # SAS e RCS já vão para a tela pelos botões de toque (Transmissor), e
        # a falta de carga elétrica e de monopropelente é só do painel.
        estado = {chave: linha for chave, linha in luzes.items() if chave not in ("SAS", "RCS", "SEMEC", "SEMMP")}
        estado["PAG"] = f"PAG {self.pagina}"
        estado["SASE"] = "SASE OFF" if erro is None or not sas else f"SASE {round(erro * 10)}"
        estado.update(self.menu.linhas())
        return estado
