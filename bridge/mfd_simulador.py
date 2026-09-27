"""Simulador da tela multifunção (mikromedia for ARM, 320x240 com touch).

Faz no PC o papel do firmware da mikromedia: recebe as mensagens do protocolo
(ATT, ALT, SAS...) como se tivessem chegado pela serial, desenha a tela e,
quando alguém toca num botão, responde TOQUE <nome>. O mfd.py conversa com
ele exatamente como vai conversar com a placa: enviar() e linhas(), igual à
classe Painel da ponte.

O desenho daqui é a referência do firmware: as posições, os tamanhos e as
cores são os que a placa vai usar. A janela só aumenta os pontos (--zoom),
sem suavizar, para parecer com a tela de verdade.

Layout, inspirado na navball do KSP2 (os números do rumo e do pitch ficam
na própria navball):

    ACEL                                V VERT
     |          .-----------.             | +100
     |        .'  N  30  60  '.           |  +10
     | [VEL ORB ]     -W-     [ ALT     ] |
     | [2287 m/s]             [ 84321 m ] |  -10
     |        '.   -30       .'           | -100
     |          '-(RCS)-(SAS)-'           |
    45%   AP  85123 m  T-00:27:53
          PE  71234 m  T-00:11:41
"""

import math
import os
import sys
import time

# Cala a propaganda que o pygame imprime ao ser importado.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

import navball

LARGURA, ALTURA = 320, 240
MAX_LINHA = 31          # linhas maiores são descartadas inteiras, como no painel
SEM_SINAL = 1.0         # s sem mensagem válida: a tela mostra que perdeu o sinal
QUADROS_POR_SEGUNDO = 30
DESTAQUE_TOQUE = 0.2    # s que o botão fica com a borda acesa depois do toque

# ---- Layout, em pontos da tela (origem no canto superior esquerdo) ----

BOLA_X, BOLA_Y, BOLA_RAIO = 160, 98, 72
ARO_RAIO = 76           # o aro escuro em volta da bola

CAIXA_VEL = pygame.Rect(20, 82, 80, 32)      # tocar nela troca o modo
CAIXA_ALT = pygame.Rect(220, 82, 80, 32)

# Barras verticais nas bordas. Na placa, preencher um retângulo é muito mais
# rápido que desenhar um arco ponto a ponto.
BARRA_ACEL = pygame.Rect(6, 30, 10, 156)
BARRA_VV = pygame.Rect(304, 30, 10, 156)
VV_MAX = 1000           # m/s no fim da barra; a escala é logarítmica

PAINEL = pygame.Rect(48, 198, 224, 40)       # informações do modo, embaixo

BOTOES_REDONDOS = {"RCS": (140, 181), "SAS": (180, 181)}
RAIO_BOTAO = 13

# Onde cada toque vale: o botão MODO é a caixa da velocidade, como no KSP2.
BOTOES = {
    "MODO": CAIXA_VEL,
    **{
        nome: pygame.Rect(x - RAIO_BOTAO, y - RAIO_BOTAO, 2 * RAIO_BOTAO, 2 * RAIO_BOTAO)
        for nome, (x, y) in BOTOES_REDONDOS.items()
    },
}


def rgb565(r, g, b):
    """A cor mais próxima que a tela de 16 bits consegue mostrar."""
    return (r & 0xF8, g & 0xFC, b & 0xF8)


FUNDO = rgb565(6, 10, 22)
TEXTO = rgb565(240, 240, 240)
ROTULO = rgb565(130, 150, 200)
ARO = rgb565(22, 32, 60)
BORDA = rgb565(60, 80, 140)
TRACO = rgb565(110, 140, 210)
COR_VEL = rgb565(235, 190, 40)
COR_ALT = rgb565(225, 70, 200)
COR_ACEL = rgb565(90, 120, 255)
VV_SOBE = rgb565(60, 200, 90)
VV_DESCE = rgb565(240, 200, 40)
VV_DESCE_RAPIDO = rgb565(240, 60, 40)
BOTAO_APAGADO = rgb565(40, 50, 80)
BOTAO_LIGADO = rgb565(40, 170, 80)
BORDA_LIGADO = rgb565(130, 240, 150)
NAVE = rgb565(255, 140, 0)
AVISO = rgb565(230, 60, 40)
NUMERO_RUMO = rgb565(255, 255, 255)
NUMERO_PITCH = rgb565(200, 215, 240)
SOMBRA_NUMERO = rgb565(10, 15, 30)
TRANSPARENTE = rgb565(255, 0, 255)  # fora do círculo da bola; não é desenhado

# Marcadores, com as cores do KSP.
COR_PRO = rgb565(230, 210, 40)
COR_NRM = rgb565(200, 70, 255)
COR_RDL = rgb565(60, 210, 230)
COR_TGT = rgb565(255, 140, 200)
COR_MNV = rgb565(60, 130, 255)
COR_FBW = rgb565(90, 230, 90)    # o ponto do fly by wire (scripts/fbw.py)

# Painel de sistemas de controle: azul armado, verde ligado, âmbar atenção.
AZUL = rgb565(76, 157, 255)
VERDE = rgb565(70, 211, 127)
AMBAR = rgb565(242, 169, 59)
APAGADO = rgb565(85, 92, 99)
FUNDO_MODO = rgb565(17, 23, 29)

# Páginas do painel de sistemas de controle, no lugar da navball enquanto o
# painel é mexido (PAG SAS e PAG AP). A roda do SAS: os seis modos em volta
# da nave, e embaixo os que não têm par na roda.
RODA_X, RODA_Y, RODA_RAIO = 160, 104, 78
RODA_MODOS = 52         # raio em que ficam os modos
RODA_BOTAO = 14
MODOS_RODA = {"NRM": -90, "PRO": -30, "RFORA": 30, "ANRM": 90, "RETRO": 150, "RDENTRO": -150}
MODOS_FAIXA = ("ESTAB", "MAN", "ALVO", "AALVO")
FAIXA = pygame.Rect(72, 190, 40, 28)
FAIXA_PASSO = 46
LINHAS_AP = ("HDG", "ALT", "VS")
NOMES_AP = {"HDG": "HDG", "ALT": "ALT", "VS": "V/S"}
ESTADO_AP = {0: ("DESLIGADO", APAGADO), 1: ("LIGADO", VERDE), 2: ("ARMADO", AZUL)}
# Alarme de estol (alpha floor do fly by wire): dois bipes por segundo.
ALARME_HZ = 880
ALARME_BIPE = 0.12      # s de cada bipe
ALARME_VAO = 0.08       # s entre os dois
ALARME_REPETE = 1.0     # s

LEIS = {
    "FBW": ("LEI FBW", VERDE),
    "DIRETA": ("LEI DIRETA", AMBAR),
    "CHAO": ("NO CHAO", APAGADO),
    "OFF": ("FBW FECHADO", APAGADO),
}

# Números pintados na navball. O rumo vai a cada 30°, logo acima do
# horizonte, com letras nos pontos cardeais (L = leste, O = oeste). O pitch
# vai a cada 30°, um pouco ao lado dos meridianos de N, L, S e O.
# A página do pouso (PAG POUSO), aberta pelo korry POUSO do painel de scripts:
# a nave desce pela linha tracejada até o alvo no chão, na altura do pé numa
# escala logarítmica (cada década, 1, 10, 100 e 1000 m, ocupa o mesmo pedaço).
POUSO_CHAO = 200            # y do chão
POUSO_TOPO = 58             # y do pé da nave a POUSO_ALT_MAX
POUSO_ALT_MAX = 10_000      # m
CHAO_POUSO = rgb565(16, 24, 40)
ALVO_POUSO = rgb565(220, 40, 70)
TRACEJADO = rgb565(40, 150, 220)
CORPO_NAVE = rgb565(200, 206, 212)
CHAMA = rgb565(255, 190, 40)
CHAMA_MEIO = rgb565(255, 245, 190)
# Fase do pouso (POU FASE) e estado do script (SCR POUSO) → texto e cor do indicador.
FASES_POUSO = {
    "QUEDA": ("QUEDA", AZUL),        # armado: esperando a hora de acender
    "QUEIMA": ("QUEIMA", VERDE),
    "TOQUE": ("TOQUE", VERDE),
    "POUSADA": ("POUSADA", VERDE),
}
FINS_POUSO = {"FIM": ("POUSADA", VERDE), "ABORT": ("ABORTADO", AVISO), "FALHA": ("FALHOU", AVISO)}
AVISOS_POUSO = {"EMPUXO": "EMPUXO INSUFICIENTE", "MOTOR": "SEM MOTOR ATIVO", "NARIZ": "NARIZ LONGE DA VERTICAL"}
CAMPOS_POUSO = ("FASE", "ALT", "VV", "MOTOR", "TWR", "FREADA", "IGN", "SAS", "INCL", "AVISO")
CAMPOS_POUSO_TEXTO = ("FASE", "SAS", "AVISO")

CARDEAIS = {0: "N", 90: "L", 180: "S", 270: "O"}
NUMEROS_RUMO = tuple((CARDEAIS.get(h, str(h)), 4, h) for h in range(0, 360, 30))
NUMEROS_PITCH = tuple(
    (str(p), p, h + 6) for h in (0, 90, 180, 270) for p in (60, 30, -30, -60)
)
VISIVEL_MIN = 0.3       # perto da borda da bola (z pequeno) o número ficaria amassado

# Marcadores que dependem do modo e números que só existem em alguns modos:
# a tela os apaga quando o modo muda.
MARCADORES_DO_MODO = ("PRO", "NRM", "RDL")
NUMEROS_DO_MODO = ("VEL", "AP", "PE", "TAP", "TPE", "DIST")
NUMEROS_OFF = ("AP", "PE", "TAP", "TPE", "DIST")   # aceitam OFF


def _inteiro(texto):
    """O inteiro escrito no texto, ou None. Só aceita dígitos com sinal opcional."""
    corpo = texto[1:] if texto[:1] in ("+", "-") else texto
    if corpo.isascii() and corpo.isdigit():
        return int(texto)
    return None


def formatar_distancia(metros):
    """No máximo 9 caracteres, para caber nas caixas."""
    if metros is None:
        return "---"
    if abs(metros) < 100_000:
        return f"{metros} m"
    if abs(metros) < 10_000_000:
        return f"{metros / 1000:.1f} km"
    if abs(metros) < 1_000_000_000:
        return f"{metros / 1000:.0f} km"
    return f"{metros / 1_000_000:.0f} Mm"


def formatar_velocidade(decimos):
    if decimos is None:
        return "---"
    sinal = "-" if decimos < 0 else ""
    decimos = abs(decimos)
    if decimos < 10_000:  # abaixo de 1000 m/s, com uma casa decimal
        return f"{sinal}{decimos // 10}.{decimos % 10} m/s"
    return f"{sinal}{decimos // 10} m/s"


def formatar_tempo(segundos):
    if segundos is None:
        return "T- ---"
    horas, resto = divmod(segundos, 3600)
    if horas >= 100:
        return f"T-{horas}h"
    return f"T-{horas:02d}:{resto // 60:02d}:{resto % 60:02d}"


class Simulador:
    """A tela multifunção numa janela do PC."""

    def __init__(self, zoom=2):
        # Só a tela e as fontes; o som do pygame não é usado.
        pygame.display.init()
        pygame.font.init()
        self._zoom = zoom
        self._janela = pygame.display.set_mode((LARGURA * zoom, ALTURA * zoom))
        pygame.display.set_caption("Tela multifuncao (simulador)")
        self._tela = pygame.Surface((LARGURA, ALTURA))
        fontes = "consolas,dejavusansmono,couriernew,monospace"
        self._fonte = pygame.font.SysFont(fontes, 14)
        self._fonte_pequena = pygame.font.SysFont(fontes, 11)
        self._fonte_media = pygame.font.SysFont(fontes, 16)
        self._fonte_grande = pygame.font.SysFont(fontes, 20)

        # O que a tela sabe, só a partir das mensagens. None = ainda não chegou.
        self._atitude = None       # (pitch, rumo, rolagem) em graus
        self._marcadores = dict.fromkeys(("PRO", "NRM", "RDL", "TGT", "MNV", "FBW"))  # (pitch, rumo)
        self._altitude = None      # ("ALT" ou "RAD", metros)
        self._numeros = dict.fromkeys(NUMEROS_DO_MODO + ("VV", "ACEL"))
        self._estados = {"SAS": None, "RCS": None, "MODO": None}
        # Painel de sistemas de controle.
        self._pagina = "NAV"
        self._sas = {"modo": None, "cor": None, "erro": None}   # erro em décimos de grau
        self._ap = {nome: [0, None] for nome in LINHAS_AP}      # [estado, valor]
        self._cursor = ("HDG", False)                           # (linha, escolhida)
        self._lei = "OFF"
        self._trava = None
        self._estol = False
        # Painel de scripts: o estado do korry POUSO e o que o pouso.py manda.
        self._scr = ("OFF", None)      # (estado, segundos que faltam segurando)
        self._pouso = dict.fromkeys(CAMPOS_POUSO)
        self._proximo_alarme = 0.0
        self._alarme = self._preparar_alarme()

        self._ultima_valida = float("-inf")
        self._toque = (None, float("-inf"))   # último botão tocado e quando
        self._proximo_quadro = 0.0
        self._saida = ["READY"]    # como a placa, avisa que acabou de ligar

    @staticmethod
    def _preparar_alarme():
        """Dois bipes agudos, o alarme de estol. None se o PC não tem som."""
        try:
            import numpy
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            taxa = pygame.mixer.get_init()[0]
            t = numpy.arange(int(taxa * ALARME_BIPE)) / taxa
            bipe = (numpy.sign(numpy.sin(2 * numpy.pi * ALARME_HZ * t)) * 5000).astype(numpy.int16)
            vao = numpy.zeros(int(taxa * ALARME_VAO), dtype=numpy.int16)
            onda = numpy.concatenate([bipe, vao, bipe])
            if pygame.mixer.get_init()[2] == 2:
                onda = numpy.column_stack([onda, onda])
            return pygame.sndarray.make_sound(onda)
        except (pygame.error, ImportError) as e:
            print(f"Simulador sem som (o alarme de estol não vai tocar): {e}")
            return None

    # ---- a mesma interface da classe Painel (ponte.py) ----

    def enviar(self, mensagem):
        """PC → tela: o que a placa receberia pela serial, sem o '\\n'."""
        if len(mensagem) > MAX_LINHA:
            return
        if self._interpretar(mensagem):
            self._ultima_valida = time.monotonic()
        else:
            self._saida.append(f"ERR {mensagem}")

    def linhas(self):
        """Tela → PC: devolve as linhas que a tela mandou desde a última chamada.

        Também é aqui que a janela anda: lê o mouse e redesenha. Por isso quem
        usa o simulador precisa chamar linhas() várias vezes por segundo, como
        já faz com a serial do painel.
        """
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                print("Janela da tela fechada.")
                sys.exit(0)
            if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                self._tocar(evento.pos[0] // self._zoom, evento.pos[1] // self._zoom)

        agora = time.monotonic()
        com_sinal = agora - self._ultima_valida < SEM_SINAL
        if self._alarme is not None and self._estol and com_sinal and agora >= self._proximo_alarme:
            self._alarme.play()
            self._proximo_alarme = agora + ALARME_REPETE
        if agora >= self._proximo_quadro:
            self._desenhar(agora)
            self._proximo_quadro = agora + 1 / QUADROS_POR_SEGUNDO

        saida, self._saida = self._saida, []
        return saida

    def esperar_ready(self):
        return True

    def fechar(self):
        pygame.quit()

    # ---- o "firmware" ----

    def _interpretar(self, mensagem):
        """Atualiza o estado da tela com uma mensagem. Devolve False se não entendeu."""
        nome, _, resto = mensagem.partition(" ")
        partes = resto.split(" ") if resto else []
        numeros = [_inteiro(p) for p in partes]
        tudo_numero = bool(numeros) and None not in numeros

        if nome == "ATT" and len(partes) == 3 and tudo_numero:
            self._atitude = tuple(n / 10 for n in numeros)
        elif nome in self._marcadores and partes == ["OFF"]:
            self._marcadores[nome] = None
        elif nome in self._marcadores and len(partes) == 2 and tudo_numero:
            self._marcadores[nome] = tuple(n / 10 for n in numeros)
        elif nome in ("ALT", "RAD") and len(partes) == 1 and tudo_numero:
            self._altitude = (nome, numeros[0])
        elif nome in NUMEROS_OFF and partes == ["OFF"]:
            self._numeros[nome] = None
        elif nome in self._numeros and len(partes) == 1 and tudo_numero:
            self._numeros[nome] = numeros[0]
        elif nome in ("SAS", "RCS") and partes in (["0"], ["1"]):
            self._estados[nome] = partes[0] == "1"
        elif nome == "PAG" and partes in (["NAV"], ["SAS"], ["AP"], ["POUSO"]):
            self._pagina = partes[0]
        elif nome == "SASM" and partes == ["OFF"]:
            self._sas["modo"] = self._sas["cor"] = None
        elif nome == "SASM" and len(partes) == 2 and partes[1] in ("A", "V"):
            self._sas["modo"], self._sas["cor"] = partes
        elif nome == "SASE" and (partes == ["OFF"] or (len(partes) == 1 and tudo_numero)):
            self._sas["erro"] = None if partes == ["OFF"] else numeros[0]
        elif nome == "APL" and len(partes) == 2 and partes[0] in self._ap and partes[1] in ("0", "1", "2"):
            self._ap[partes[0]][0] = numeros[1]
        elif nome == "APV" and len(partes) == 2 and partes[0] in self._ap and numeros[1] is not None:
            self._ap[partes[0]][1] = numeros[1]
        elif nome == "APC" and len(partes) == 2 and partes[0] in self._ap and partes[1] in ("0", "1"):
            self._cursor = (partes[0], partes[1] == "1")
        elif nome == "SCR" and len(partes) == 2 and partes[0] == "POUSO" and partes[1] in ("OFF", "ATIVO", "FIM", "ABORT", "FALHA"):
            self._scr = (partes[1], None)
        elif nome == "SCR" and len(partes) == 3 and partes[0] == "POUSO" and partes[1] in ("LIGA", "DESL") and numeros[2] is not None:
            self._scr = (partes[1], numeros[2])
        elif nome == "POU" and partes == ["OFF"]:
            self._pouso = dict.fromkeys(CAMPOS_POUSO)
        elif nome == "POU" and len(partes) == 2 and partes[0] in CAMPOS_POUSO_TEXTO:
            self._pouso[partes[0]] = partes[1]
        elif nome == "POU" and len(partes) == 2 and partes[0] in CAMPOS_POUSO and (numeros[1] is not None or partes[1] == "OFF"):
            self._pouso[partes[0]] = numeros[1]
        elif nome == "LEI" and len(partes) == 1 and partes[0] in LEIS:
            self._lei = partes[0]
        elif nome == "ESTOL" and partes in (["0"], ["1"]):
            self._estol = partes[0] == "1"
        elif nome == "TRAVA" and (partes == ["OFF"] or (len(partes) == 1 and tudo_numero)):
            self._trava = None if partes == ["OFF"] else numeros[0]
        elif nome == "MODO" and partes in (["SUP"], ["ORB"], ["ALVO"]):
            if partes[0] != self._estados["MODO"]:
                # Os números e os marcadores do modo antigo não valem mais;
                # os do modo novo chegam logo em seguida.
                self._numeros.update(dict.fromkeys(NUMEROS_DO_MODO))
                self._marcadores.update(dict.fromkeys(MARCADORES_DO_MODO))
            self._estados[nome] = partes[0]
        else:
            return False
        return True

    def _tocar(self, x, y):
        if self._pagina != "NAV":
            return   # as páginas do painel de sistemas são só para ver
        for nome, retangulo in BOTOES.items():
            if nome in BOTOES_REDONDOS:
                cx, cy = BOTOES_REDONDOS[nome]
                dentro = (x - cx) ** 2 + (y - cy) ** 2 <= RAIO_BOTAO**2
            else:
                dentro = retangulo.collidepoint(x, y)
            if dentro:
                self._saida.append(f"TOQUE {nome}")
                self._toque = (nome, time.monotonic())

    # ---- desenho ----

    def _desenhar(self, agora):
        self._tela.fill(FUNDO)
        com_sinal = agora - self._ultima_valida < SEM_SINAL
        if com_sinal and self._pagina == "SAS":
            self._desenhar_pagina_sas()
        elif com_sinal and self._pagina == "AP":
            self._desenhar_pagina_ap()
        elif com_sinal and self._pagina == "POUSO":
            self._desenhar_pagina_pouso(agora)
        else:
            self._desenhar_aro()
            self._desenhar_navball(com_sinal)
            self._desenhar_caixas(com_sinal, agora)
            self._desenhar_barras(com_sinal)
            self._desenhar_botoes(com_sinal, agora)
            self._desenhar_painel(com_sinal)
        ampliada = pygame.transform.scale(self._tela, self._janela.get_size())
        self._janela.blit(ampliada, (0, 0))
        pygame.display.flip()

    def _texto(self, texto, cor, canto=None, centro=None, direita=None, fonte=None):
        """Escreve com o canto superior esquerdo, o centro ou o canto superior direito no ponto dado."""
        imagem = (fonte or self._fonte).render(texto, True, cor)
        retangulo = imagem.get_rect()
        if centro is not None:
            retangulo.center = centro
        elif direita is not None:
            retangulo.topright = direita
        else:
            retangulo.topleft = canto
        self._tela.blit(imagem, retangulo)

    def _na_bola(self, x, y):
        """Ponto da tela para as coordenadas (x, y) da bola, de -1 a 1."""
        return (round(BOLA_X + x * BOLA_RAIO), round(BOLA_Y - y * BOLA_RAIO))

    def _desenhar_aro(self):
        pygame.draw.circle(self._tela, ARO, (BOLA_X, BOLA_Y), ARO_RAIO)
        pygame.draw.circle(self._tela, BORDA, (BOLA_X, BOLA_Y), ARO_RAIO, 1)

    def _desenhar_navball(self, com_sinal):
        if not com_sinal or self._atitude is None:
            pygame.draw.circle(self._tela, BOTAO_APAGADO, (BOLA_X, BOLA_Y), BOLA_RAIO)
            self._texto("SEM SINAL", AVISO, centro=(BOLA_X, BOLA_Y - 20))
            return

        pitch, rumo, rolagem = self._atitude
        base = navball.base_da_nave(pitch, rumo, rolagem)
        imagem = navball.desenhar(BOLA_RAIO, base, TRANSPARENTE)
        # A imagem vem como (linha, coluna); o pygame quer (coluna, linha).
        # Os cantos do quadrado, fora do círculo, não são desenhados: na
        # placa, o laço já pula os pontos fora da bola.
        bola = pygame.surfarray.make_surface(imagem.swapaxes(0, 1))
        bola.set_colorkey(TRANSPARENTE)
        self._tela.blit(bola, (BOLA_X - BOLA_RAIO, BOLA_Y - BOLA_RAIO))

        # Os números ficam sempre de pé na tela, sem girar com a bola: na
        # placa, é só escrever com a fonte normal no ponto projetado. Uma
        # sombra escura, 1 ponto abaixo e à direita, separa o número da grade.
        for numeros, cor in ((NUMEROS_PITCH, NUMERO_PITCH), (NUMEROS_RUMO, NUMERO_RUMO)):
            for texto, pitch_numero, rumo_numero in numeros:
                x, y, z = navball.projetar(base, navball.direcao(pitch_numero, rumo_numero))
                if z > VISIVEL_MIN:
                    cx, cy = self._na_bola(x, y)
                    self._texto(texto, SOMBRA_NUMERO, centro=(cx + 1, cy + 1), fonte=self._fonte_pequena)
                    self._texto(texto, cor, centro=(cx, cy), fonte=self._fonte_pequena)

        # Cada marcador tem um par do lado oposto da bola (menos a manobra e
        # o ponto do FBW).
        # Um marcador só aparece se estiver na metade visível da bola. A
        # ordem é a de desenho: o último fica por cima.
        pares = (
            ("RDL", self._radial_fora, self._radial_dentro),
            ("NRM", self._normal, self._antinormal),
            ("TGT", self._alvo, self._antialvo),
            ("FBW", self._ponto_fbw, None),   # antes do pró-grado, que fica por cima quando os dois se alinham
            ("PRO", self._progrado, self._retrogrado),
            ("MNV", self._manobra, None),
        )
        for nome, desenho, desenho_oposto in pares:
            if self._marcadores[nome] is None:
                continue
            p, r = self._marcadores[nome]
            direcoes = [(navball.direcao(p, r), desenho)]
            if desenho_oposto is not None:
                direcoes.append((navball.direcao(-p, r + 180), desenho_oposto))
            for vetor, desenhar in direcoes:
                x, y, z = navball.projetar(base, vetor)
                if z > 0:
                    desenhar(self._na_bola(x, y))

        self._simbolo_nave()

    # ---- marcadores: 6 pontos de raio, com hastes ----

    def _circulo_com_hastes(self, centro, cor, angulos, de, ate):
        cx, cy = centro
        pygame.draw.circle(self._tela, cor, centro, 6, 2)
        for a in angulos:
            dx, dy = math.cos(math.radians(a)), -math.sin(math.radians(a))
            pygame.draw.line(self._tela, cor, (cx + de * dx, cy + de * dy), (cx + ate * dx, cy + ate * dy), 2)

    def _progrado(self, centro):
        self._circulo_com_hastes(centro, COR_PRO, (0, 90, 180), 6, 11)
        pygame.draw.circle(self._tela, COR_PRO, centro, 1)

    def _retrogrado(self, centro):
        self._circulo_com_hastes(centro, COR_PRO, (45, 135, 225, 315), 1, 5)
        self._circulo_com_hastes(centro, COR_PRO, (90, 225, 315), 6, 11)

    def _triangulo(self, centro, cor, para_cima):
        cx, cy = centro
        s = -1 if para_cima else 1
        pontos = [(cx, cy + 7 * s), (cx - 7, cy - 5 * s), (cx + 7, cy - 5 * s)]
        pygame.draw.polygon(self._tela, cor, pontos, 2)
        return pontos

    def _normal(self, centro):
        self._triangulo(centro, COR_NRM, para_cima=True)
        pygame.draw.circle(self._tela, COR_NRM, centro, 1)

    def _antinormal(self, centro):
        for ponta in self._triangulo(centro, COR_NRM, para_cima=False):
            pygame.draw.line(self._tela, COR_NRM, centro, ponta, 1)

    def _radial_fora(self, centro):
        self._circulo_com_hastes(centro, COR_RDL, (45, 135, 225, 315), 6, 11)
        pygame.draw.circle(self._tela, COR_RDL, centro, 1)

    def _radial_dentro(self, centro):
        self._circulo_com_hastes(centro, COR_RDL, (45, 135, 225, 315), 2, 6)

    def _alvo(self, centro):
        self._circulo_com_hastes(centro, COR_TGT, (0, 90, 180, 270), 6, 11)
        pygame.draw.circle(self._tela, COR_TGT, centro, 1)

    def _antialvo(self, centro):
        self._circulo_com_hastes(centro, COR_TGT, (45, 135, 225, 315), 1, 5)

    def _manobra(self, centro):
        self._circulo_com_hastes(centro, COR_MNV, (90, 210, 330), 6, 11)
        pygame.draw.circle(self._tela, COR_MNV, centro, 3)

    def _ponto_fbw(self, centro):
        """Quatro cantos de um quadrado: com o avião no ponto, o pró-grado fica
        dentro dele, e as hastes do pró-grado passam pelos vãos."""
        cx, cy = centro
        for sx in (-1, 1):
            for sy in (-1, 1):
                canto = (cx + 8 * sx, cy + 8 * sy)
                pygame.draw.line(self._tela, COR_FBW, canto, (cx + 4 * sx, cy + 8 * sy), 2)
                pygame.draw.line(self._tela, COR_FBW, canto, (cx + 8 * sx, cy + 4 * sy), 2)
        pygame.draw.circle(self._tela, COR_FBW, centro, 1)

    def _simbolo_nave(self):
        """O "W" laranja no centro: para onde o nariz aponta. Fica sempre parado."""
        cx, cy = BOLA_X, BOLA_Y
        pygame.draw.line(self._tela, NAVE, (cx - 24, cy), (cx - 9, cy), 3)
        pygame.draw.line(self._tela, NAVE, (cx + 9, cy), (cx + 24, cy), 3)
        pygame.draw.lines(self._tela, NAVE, False, [(cx - 9, cy), (cx, cy + 7), (cx + 9, cy)], 3)
        pygame.draw.circle(self._tela, NAVE, (cx, cy - 3), 2)

    # ---- páginas do painel de sistemas de controle ----

    def _marcador_do_modo(self, modo, centro):
        if modo == "ESTAB":
            # Segura a atitude de agora: não tem marcador na navball.
            cx, cy = centro
            pygame.draw.circle(self._tela, TEXTO, centro, 7, 2)
            pygame.draw.line(self._tela, TEXTO, (cx - 4, cy), (cx + 4, cy), 2)
            return
        desenhos = {
            "PRO": self._progrado, "RETRO": self._retrogrado, "NRM": self._normal,
            "ANRM": self._antinormal, "RFORA": self._radial_fora, "RDENTRO": self._radial_dentro,
            "ALVO": self._alvo, "AALVO": self._antialvo, "MAN": self._manobra,
        }
        desenhos[modo](centro)

    def _disponivel(self, modo):
        """Alvo e manobra só existem com um alvo ou um nó, como os marcadores da navball."""
        if modo in ("ALVO", "AALVO"):
            return self._marcadores["TGT"] is not None
        if modo == "MAN":
            return self._marcadores["MNV"] is not None
        return True

    def _botao_de_modo(self, modo, centro, raio):
        escolhido = self._sas["modo"] == modo
        cor = (VERDE if self._sas["cor"] == "V" else AZUL) if escolhido else None
        centro = (round(centro[0]), round(centro[1]))
        if cor:
            pygame.draw.circle(self._tela, cor, centro, raio + 4, 2)
        pygame.draw.circle(self._tela, FUNDO_MODO, centro, raio)
        pygame.draw.circle(self._tela, cor or BORDA, centro, raio, 3 if cor else 1)
        if self._disponivel(modo):
            self._marcador_do_modo(modo, centro)
        else:
            self._texto("--", APAGADO, centro=centro, fonte=self._fonte_pequena)

    def _desenhar_pagina_sas(self):
        s, ligado = self._sas, self._estados["SAS"]
        self._texto("SAS", ROTULO, canto=(8, 4), fonte=self._fonte_pequena)
        self._texto("LIGADO" if ligado else "DESLIGADO", VERDE if ligado else APAGADO, canto=(8, 17))
        self._texto("ERRO", ROTULO, direita=(312, 4), fonte=self._fonte_pequena)
        erro = "---" if s["erro"] is None else f"{s['erro'] / 10:.1f}"
        cor_erro = VERDE if s["cor"] == "V" else AZUL if s["cor"] == "A" else APAGADO
        self._texto(erro, cor_erro, direita=(312, 17))

        pygame.draw.circle(self._tela, ARO, (RODA_X, RODA_Y), RODA_RAIO)
        pygame.draw.circle(self._tela, BORDA, (RODA_X, RODA_Y), RODA_RAIO, 1)
        posicoes = {}
        for modo, angulo in MODOS_RODA.items():
            a = math.radians(angulo)
            posicoes[modo] = (RODA_X + RODA_MODOS * math.cos(a), RODA_Y + RODA_MODOS * math.sin(a))
            pygame.draw.line(self._tela, BORDA, (RODA_X, RODA_Y), posicoes[modo], 1)
        for modo, centro in posicoes.items():
            self._botao_de_modo(modo, centro, RODA_BOTAO)

        # A nave no centro aponta para o modo escolhido, torta enquanto ainda vira.
        if ligado and s["modo"] in MODOS_RODA:
            torto = 0 if s["cor"] == "V" else min(60, (s["erro"] or 600) / 10)
            a = math.radians(MODOS_RODA[s["modo"]] + torto)
            cor = VERDE if s["cor"] == "V" else AZUL
            ponta = (RODA_X + 22 * math.cos(a), RODA_Y + 22 * math.sin(a))
            lados = [(RODA_X + 9 * math.cos(a + d), RODA_Y + 9 * math.sin(a + d)) for d in (-2.4, 2.4)]
            pygame.draw.lines(self._tela, cor, False, [lados[0], ponta, lados[1]], 3)
        pygame.draw.circle(self._tela, NAVE, (RODA_X, RODA_Y), 3)

        for i, modo in enumerate(MODOS_FAIXA):
            caixa = FAIXA.move(i * FAIXA_PASSO, 0)
            pygame.draw.rect(self._tela, ARO, caixa, border_radius=4)
            pygame.draw.rect(self._tela, BORDA, caixa, 1, border_radius=4)
            self._botao_de_modo(modo, caixa.center, 11)
        self._texto("MODO DO SAS", ROTULO, centro=(160, 232), fonte=self._fonte_pequena)

    @staticmethod
    def _valor_ap(nome, valor):
        if valor is None:
            return "---"
        if nome == "HDG":
            return f"{valor:03d}"
        if nome == "ALT":
            return f"{valor} M"
        return f"{'+' if valor >= 0 else '-'}{abs(valor) / 10:.1f} M/S"

    def _desenhar_pagina_ap(self):
        self._texto("PILOTO AUTOMATICO", ROTULO, centro=(160, 12))
        pygame.draw.line(self._tela, BORDA, (12, 24), (308, 24), 1)
        linha_cursor, escolhida = self._cursor
        for i, nome in enumerate(LINHAS_AP):
            y = 46 + i * 44
            modo, valor = self._ap[nome]
            rotulo, cor = ESTADO_AP[modo]
            no_cursor = nome == linha_cursor
            if no_cursor:
                pygame.draw.lines(self._tela, TEXTO, False, [(12, y - 6), (20, y), (12, y + 6)], 1)
                if escolhida:
                    pygame.draw.rect(self._tela, AMBAR, (176, y - 15, 130, 30), 2, border_radius=3)
                else:
                    pygame.draw.rect(self._tela, TEXTO, (24, y - 17, 286, 34), 1, border_radius=4)
            self._texto(NOMES_AP[nome], TEXTO, canto=(32, y - 9), fonte=self._fonte_media)
            self._texto(rotulo, cor, canto=(80, y - 6), fonte=self._fonte_pequena)
            imagem = self._fonte_grande.render(self._valor_ap(nome, valor), True, AMBAR if no_cursor and escolhida else TEXTO)
            self._tela.blit(imagem, imagem.get_rect(midright=(300, y)))
        pygame.draw.line(self._tela, BORDA, (12, 184), (308, 184), 1)
        lei, cor_lei = LEIS[self._lei]
        self._texto("FBW", ROTULO, canto=(16, 194), fonte=self._fonte_pequena)
        self._texto(lei, cor_lei, canto=(48, 192))
        trava = "SEM TRAVA" if self._trava is None else f"TRAVA {self._trava} M"
        self._texto(trava, APAGADO if self._trava is None else VERDE, direita=(304, 192))
        dica = "GIRAR: VALOR  APERTAR: SAI" if escolhida else "GIRAR: LINHA  APERTAR: ESCOLHE"
        self._texto(dica, ROTULO, centro=(160, 226), fonte=self._fonte_pequena)

    def _nave_de_pouso(self, x, pe, motor, trem):
        """A nave em pé, com o pé em (x, pe): corpo, nariz, pernas e a chama do motor."""
        if motor:
            comprimento = 6 + 22 * motor / 100
            pygame.draw.polygon(self._tela, CHAMA, [(x - 3, pe - 2), (x + 3, pe - 2), (x, pe + comprimento)])
            pygame.draw.polygon(self._tela, CHAMA_MEIO, [(x - 1, pe - 2), (x + 1, pe - 2), (x, pe + comprimento * 0.55)])
        pygame.draw.rect(self._tela, CORPO_NAVE, (x - 3, pe - 38, 7, 34))
        pygame.draw.rect(self._tela, APAGADO, (x - 3, pe - 38, 7, 34), 1)
        pygame.draw.line(self._tela, APAGADO, (x - 3, pe - 22), (x + 3, pe - 22), 1)
        pygame.draw.polygon(self._tela, CORPO_NAVE, [(x - 3, pe - 38), (x + 3, pe - 38), (x, pe - 45)])
        pygame.draw.rect(self._tela, APAGADO, (x - 2, pe - 4, 5, 3))    # sino do motor
        if trem:
            for lado in (-1, 1):
                pygame.draw.line(self._tela, TEXTO, (x + 3 * lado, pe - 12), (x + 9 * lado, pe), 1)
        else:
            for lado in (-1, 1):
                pygame.draw.line(self._tela, TEXTO, (x + 3 * lado, pe - 12), (x + 5 * lado, pe - 3), 1)

    def _desenhar_pagina_pouso(self, agora):
        p = self._pouso
        estado, faltam = self._scr

        # Chão e alvo
        pygame.draw.ellipse(self._tela, CHAO_POUSO, (-160, POUSO_CHAO - 8, 640, 200))
        for largura, altura, espessura in ((76, 16, 3), (44, 9, 3)):
            pygame.draw.ellipse(self._tela, ALVO_POUSO, (160 - largura // 2, POUSO_CHAO + 4 - altura // 2, largura, altura), espessura)
        pygame.draw.circle(self._tela, ALVO_POUSO, (160, POUSO_CHAO + 4), 2)

        # A nave, na altura do pé, e o tracejado até o alvo
        if p["ALT"] is not None:
            metros = max(0.0, p["ALT"] / 10)
            fracao = math.log10(1 + min(metros, POUSO_ALT_MAX)) / math.log10(1 + POUSO_ALT_MAX)
            pe = round(POUSO_CHAO + 4 - fracao * (POUSO_CHAO + 4 - POUSO_TOPO))
            for y in range(pe + 4, POUSO_CHAO, 8):
                pygame.draw.line(self._tela, TRACEJADO, (160, y), (160, min(y + 4, POUSO_CHAO)), 1)
            trem = p["FASE"] in ("QUEIMA", "TOQUE", "POUSADA")
            self._nave_de_pouso(160, pe, p["MOTOR"] or 0, trem)

        # Números em cima, como na tela do booster
        pequena = self._fonte_pequena
        alt = "---" if p["ALT"] is None else (f"{p['ALT'] / 10:.1f} m" if p["ALT"] < 1000 else formatar_distancia(round(p["ALT"] / 10)))
        vel = "---" if p["VV"] is None else f"{abs(p['VV']) / 10:.1f} m/s"
        twr = "---" if p["TWR"] is None else f"{p['TWR'] / 100:.2f}"
        for i, (rotulo, valor) in enumerate((("ALT", alt), ("VEL", vel), ("TWR", twr))):
            self._texto(rotulo, ROTULO, canto=(8, 6 + i * 15))
            self._texto(valor, VERDE, canto=(44, 6 + i * 15))
        sas = p["SAS"] or "---"
        motor = "---" if p["MOTOR"] is None else f"{p['MOTOR']}%"
        incl = "---" if p["INCL"] is None else f"{p['INCL']} GR"
        for i, (rotulo, valor) in enumerate((("SAS", sas), ("MOTOR", motor), ("INCL", incl))):
            self._texto(rotulo, ROTULO, direita=(258, 6 + i * 15))
            self._texto(valor, VERDE, direita=(312, 6 + i * 15))

        # Aviso do script, piscando
        if p["AVISO"] in AVISOS_POUSO and int(agora * 2) % 2 == 0:
            self._texto(AVISOS_POUSO[p["AVISO"]], AVISO, centro=(160, 56), fonte=pequena)

        # Segurando o korry: quantos segundos faltam
        if estado in ("LIGA", "DESL"):
            acao = "PARA POUSAR" if estado == "LIGA" else "PARA ABORTAR"
            caixa = pygame.Rect(90, 80, 140, 56)
            pygame.draw.rect(self._tela, FUNDO, caixa, border_radius=6)
            pygame.draw.rect(self._tela, AMBAR, caixa, 2, border_radius=6)
            self._texto(f"SEGURE {faltam} S", AMBAR, centro=(160, 100), fonte=self._fonte_grande)
            self._texto(acao, AMBAR, centro=(160, 122), fonte=pequena)

        # Indicador da fase, embaixo à esquerda
        if estado in FINS_POUSO:
            fase, cor = FINS_POUSO[estado]
        elif estado == "LIGA":
            fase, cor = "ARMANDO", AMBAR
        elif p["FASE"] in FASES_POUSO:
            fase, cor = FASES_POUSO[p["FASE"]]
        elif estado in ("ATIVO", "DESL"):
            fase, cor = "LIGANDO", AZUL
        else:
            fase, cor = "PARADO", APAGADO
        centro = (26, 212)
        pygame.draw.circle(self._tela, cor, centro, 16, 2)
        pygame.draw.circle(self._tela, cor, centro, 7, 2)
        pygame.draw.circle(self._tela, cor, centro, 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(self._tela, cor, (centro[0] + 11 * dx, centro[1] + 11 * dy), (centro[0] + 19 * dx, centro[1] + 19 * dy), 2)
        self._texto(fase, cor, canto=(48, 203))
        pygame.draw.line(self._tela, cor, (46, 222), (118, 222), 1)

        # Freada: quanto do empuxo ela precisa agora; o motor acende na marca
        barra = pygame.Rect(212, 220, 100, 8)
        self._texto("FREADA", ROTULO, canto=(212, 204), fonte=pequena)
        freada = p["FREADA"]
        self._texto("---" if freada is None else f"{freada}%" if freada < 999 else "> 100%",
                    AVISO if freada is not None and freada > 100 else TEXTO, direita=(312, 202))
        pygame.draw.rect(self._tela, ARO, barra)
        if freada is not None:
            largura = round(barra.width * min(freada, 100) / 100)
            cor_barra = AVISO if freada > 100 else VERDE if p["FASE"] != "QUEDA" else AZUL
            pygame.draw.rect(self._tela, cor_barra, (barra.x, barra.y, largura, barra.height))
        pygame.draw.rect(self._tela, BORDA, barra, 1)
        if p["IGN"] is not None:
            x = barra.x + round(barra.width * p["IGN"] / 100)
            pygame.draw.line(self._tela, AMBAR, (x, barra.y - 3), (x, barra.bottom + 2), 2)

    # ---- caixas, barras, botões e painel ----

    def _caixa(self, retangulo, cor, titulo, valor, destacada=False):
        pygame.draw.rect(self._tela, FUNDO, retangulo, border_radius=4)
        pygame.draw.rect(self._tela, cor, retangulo, 2 if destacada else 1, border_radius=4)
        self._texto(titulo, cor, canto=(retangulo.x + 5, retangulo.y + 2), fonte=self._fonte_pequena)
        self._texto(valor, TEXTO, direita=(retangulo.right - 5, retangulo.y + 14))

    def _desenhar_caixas(self, com_sinal, agora):
        tocado, quando = self._toque
        modo = self._estados["MODO"] or "---"
        vel = formatar_velocidade(self._numeros["VEL"]) if com_sinal else "---"
        destacada = tocado == "MODO" and agora - quando < DESTAQUE_TOQUE
        self._caixa(CAIXA_VEL, COR_VEL, f"VEL {modo}", vel, destacada)

        tipo, altitude = self._altitude or ("ALT", None)
        self._caixa(
            CAIXA_ALT,
            COR_ALT,
            "RADAR" if tipo == "RAD" else "ALT",
            formatar_distancia(altitude) if com_sinal else "---",
        )

    def _desenhar_barras(self, com_sinal):
        pequena = self._fonte_pequena
        acel = self._numeros["ACEL"] if com_sinal else None
        vv = self._numeros["VV"] if com_sinal else None

        # Acelerador: enche de baixo para cima.
        b = BARRA_ACEL
        pygame.draw.rect(self._tela, ARO, b)
        if acel is not None:
            altura = round(b.height * max(0, min(100, acel)) / 100)
            pygame.draw.rect(self._tela, COR_ACEL, (b.x, b.bottom - altura, b.width, altura))
        pygame.draw.rect(self._tela, BORDA, b, 1)
        self._texto("ACEL", ROTULO, canto=(2, 4), fonte=pequena)
        self._texto("---" if acel is None else f"{acel}%", TEXTO, canto=(2, b.bottom + 4), fonte=pequena)

        # Velocidade vertical: zero no meio, escala logarítmica. Cada década
        # (1, 10, 100, 1000 m/s) ocupa o mesmo pedaço da barra.
        b = BARRA_VV
        meio = b.centery
        metade = b.height // 2

        def y_da_vv(mps):
            fracao = math.log10(1 + min(abs(mps), VV_MAX)) / math.log10(1 + VV_MAX)
            return round(meio - math.copysign(fracao * metade, mps))

        pygame.draw.rect(self._tela, ARO, b)
        if vv is not None:
            mps = vv / 10
            y = y_da_vv(mps)
            cor = VV_SOBE if mps >= 0 else VV_DESCE if mps > -10 else VV_DESCE_RAPIDO
            pygame.draw.rect(self._tela, cor, (b.x, min(y, meio), b.width, abs(y - meio) + 1))
        pygame.draw.rect(self._tela, BORDA, b, 1)
        pygame.draw.line(self._tela, TEXTO, (b.x - 3, meio), (b.right, meio), 1)
        # Sem o rótulo do zero: ele ficaria embaixo da caixa da altitude.
        for mps in (100, 10, -10, -100):
            y = y_da_vv(mps)
            pygame.draw.line(self._tela, TRACO, (b.x - 3, y), (b.x, y), 1)
            self._texto(f"{mps:+d}", ROTULO, direita=(b.x - 4, y - 6), fonte=pequena)
        self._texto("V VERT", ROTULO, direita=(LARGURA - 2, 4), fonte=pequena)

    def _desenhar_botoes(self, com_sinal, agora):
        """O botão mostra o estado do jogo, não o toque: SAS só fica verde
        quando o jogo confirma que o SAS ligou."""
        tocado, quando = self._toque
        for nome, centro in BOTOES_REDONDOS.items():
            ligado = com_sinal and self._estados[nome]
            pygame.draw.circle(self._tela, BOTAO_LIGADO if ligado else BOTAO_APAGADO, centro, RAIO_BOTAO)
            destaque = nome == tocado and agora - quando < DESTAQUE_TOQUE
            borda = TEXTO if destaque else BORDA_LIGADO if ligado else BORDA
            pygame.draw.circle(self._tela, borda, centro, RAIO_BOTAO, 2 if destaque else 1)
            self._texto(nome, TEXTO, centro=centro, fonte=self._fonte_pequena)

    def _desenhar_painel(self, com_sinal):
        """Embaixo: AP e PE no modo ORB, a distância no ALVO. No SUP o painel
        não aparece: a velocidade vertical já está na barra."""
        n = self._numeros
        modo = self._estados["MODO"]
        if not com_sinal:
            linhas = []
        elif modo == "ORB":
            linhas = [
                ("AP", formatar_distancia(n["AP"]), formatar_tempo(n["TAP"])),
                ("PE", formatar_distancia(n["PE"]), formatar_tempo(n["TPE"])),
            ]
        elif modo == "ALVO":
            linhas = [("DIST", formatar_distancia(n["DIST"]), "")]
        else:
            linhas = []
        if not linhas:
            return

        pygame.draw.rect(self._tela, BORDA, PAINEL, 1, border_radius=4)
        y = PAINEL.y + 3
        for rotulo, valor, tempo in linhas:
            self._texto(rotulo, ROTULO, canto=(PAINEL.x + 6, y + 2), fonte=self._fonte_pequena)
            self._texto(valor, TEXTO, direita=(PAINEL.x + 128, y))
            if tempo:
                self._texto(tempo, ROTULO, direita=(PAINEL.right - 5, y + 2), fonte=self._fonte_pequena)
            y += 17
