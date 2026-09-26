"""Simulador da tela multifunção (mikromedia for ARM, 320x240 com touch).

Faz no PC o papel do firmware da mikromedia: recebe as mensagens do protocolo
(ATT, ALT, SAS...) como se tivessem chegado pela serial, desenha a tela e,
quando alguém clica num botão, responde TOQUE <nome>. O mfd.py conversa com
ele exatamente como vai conversar com a placa: enviar() e linhas(), igual à
classe Painel da ponte.

O desenho daqui é a referência do firmware: as posições, os tamanhos e as
cores são os que a placa vai usar. A janela só aumenta os pontos (--zoom),
sem suavizar, para parecer com a tela de verdade.
"""

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

# Layout, em pontos da tela (origem no canto superior esquerdo).
BOLA_X, BOLA_Y, BOLA_RAIO = 112, 130, 100
COLUNA_X = 224          # coluna dos números, à direita da bola
BOTOES = {
    "SAS": pygame.Rect(224, 158, 44, 36),
    "RCS": pygame.Rect(272, 158, 44, 36),
    "MODO": pygame.Rect(224, 200, 92, 36),
}


def rgb565(r, g, b):
    """A cor mais próxima que a tela de 16 bits consegue mostrar."""
    return (r & 0xF8, g & 0xFC, b & 0xF8)


FUNDO = rgb565(0, 0, 0)
TEXTO = rgb565(235, 235, 235)
ROTULO = rgb565(130, 130, 130)
ARO = rgb565(90, 90, 90)
APAGADO = rgb565(55, 55, 55)
LIGADO = rgb565(40, 170, 70)
BOTAO_MODO = rgb565(40, 70, 120)
MARCADOR = rgb565(225, 215, 40)
NAVE = rgb565(255, 140, 0)
AVISO = rgb565(230, 60, 40)
CARDEAL = rgb565(255, 255, 255)

# Pontos cardeais desenhados logo acima do horizonte. L = leste, O = oeste.
CARDEAIS = (("N", 0), ("L", 90), ("S", 180), ("O", 270))


def _inteiro(texto):
    """O inteiro escrito no texto, ou None. Só aceita dígitos com sinal opcional."""
    corpo = texto[1:] if texto[:1] in ("+", "-") else texto
    if corpo.isascii() and corpo.isdigit():
        return int(texto)
    return None


def formatar_distancia(metros):
    if metros is None:
        return "---"
    if abs(metros) < 100_000:
        return f"{metros} m"
    if abs(metros) < 100_000_000:
        return f"{metros / 1000:.1f} km"
    return f"{metros / 1_000_000:.1f} Mm"


def formatar_velocidade(decimos):
    if decimos is None:
        return "---"
    if decimos < 10_000:  # abaixo de 1000 m/s, com uma casa decimal
        return f"{decimos // 10}.{decimos % 10} m/s"
    return f"{decimos // 10} m/s"


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
        self._fonte = pygame.font.SysFont("consolas,dejavusansmono,couriernew,monospace", 14)

        # O que a tela sabe, só a partir das mensagens. None = ainda não chegou.
        self._atitude = None       # (pitch, rumo, rolagem) em graus
        self._progrado = None      # (pitch, rumo) em graus
        self._numeros = {"ALT": None, "VEL": None, "AP": None, "PE": None}
        self._estados = {"SAS": None, "RCS": None, "MODO": None}

        self._ultima_valida = float("-inf")
        self._toque = (None, float("-inf"))   # último botão tocado e quando
        self._proximo_quadro = 0.0
        self._saida = ["READY"]    # como a placa, avisa que acabou de ligar

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
        elif nome == "PRO" and partes == ["OFF"]:
            self._progrado = None
        elif nome == "PRO" and len(partes) == 2 and tudo_numero:
            self._progrado = tuple(n / 10 for n in numeros)
        elif nome in ("AP", "PE") and partes == ["OFF"]:
            self._numeros[nome] = None
        elif nome in self._numeros and len(partes) == 1 and tudo_numero:
            self._numeros[nome] = numeros[0]
        elif nome in ("SAS", "RCS") and partes in (["0"], ["1"]):
            self._estados[nome] = partes[0] == "1"
        elif nome == "MODO" and partes in (["SUP"], ["ORB"]):
            self._estados[nome] = partes[0]
        else:
            return False
        return True

    def _tocar(self, x, y):
        for nome, retangulo in BOTOES.items():
            if retangulo.collidepoint(x, y):
                self._saida.append(f"TOQUE {nome}")
                self._toque = (nome, time.monotonic())

    # ---- desenho ----

    def _desenhar(self, agora):
        self._tela.fill(FUNDO)
        com_sinal = agora - self._ultima_valida < SEM_SINAL
        self._desenhar_navball(com_sinal)
        self._desenhar_numeros(com_sinal)
        self._desenhar_botoes(com_sinal, agora)
        ampliada = pygame.transform.scale(self._tela, self._janela.get_size())
        self._janela.blit(ampliada, (0, 0))
        pygame.display.flip()

    def _texto(self, texto, cor, canto=None, centro=None):
        imagem = self._fonte.render(texto, True, cor)
        retangulo = imagem.get_rect()
        if centro is not None:
            retangulo.center = centro
        else:
            retangulo.topleft = canto
        self._tela.blit(imagem, retangulo)

    def _na_bola(self, x, y):
        """Ponto da tela para as coordenadas (x, y) da bola, de -1 a 1."""
        return (round(BOLA_X + x * BOLA_RAIO), round(BOLA_Y - y * BOLA_RAIO))

    def _desenhar_navball(self, com_sinal):
        if not com_sinal or self._atitude is None:
            pygame.draw.circle(self._tela, APAGADO, (BOLA_X, BOLA_Y), BOLA_RAIO)
            self._texto("SEM SINAL", AVISO, centro=(BOLA_X, BOLA_Y))
            self._texto("RUMO ---", TEXTO, centro=(BOLA_X, 12))
            return

        pitch, rumo, rolagem = self._atitude
        base = navball.base_da_nave(pitch, rumo, rolagem)
        imagem = navball.desenhar(BOLA_RAIO, base, FUNDO)
        # A imagem vem como (linha, coluna); o pygame quer (coluna, linha).
        bola = pygame.surfarray.make_surface(imagem.swapaxes(0, 1))
        self._tela.blit(bola, (BOLA_X - BOLA_RAIO, BOLA_Y - BOLA_RAIO))
        pygame.draw.circle(self._tela, ARO, (BOLA_X, BOLA_Y), BOLA_RAIO + 2, 2)

        for letra, rumo_cardeal in CARDEAIS:
            x, y, z = navball.projetar(base, navball.direcao(5, rumo_cardeal))
            if z > 0.3:  # perto da borda a letra ficaria em cima do aro
                self._texto(letra, CARDEAL, centro=self._na_bola(x, y))

        # Pró-grado (para onde a nave vai) e retrógrado (o oposto). Um marcador
        # só aparece se estiver na metade visível da bola.
        if self._progrado is not None:
            p, r = self._progrado
            for vetor, desenho in (
                (navball.direcao(p, r), self._marcador_progrado),
                (navball.direcao(-p, r + 180), self._marcador_retrogrado),
            ):
                x, y, z = navball.projetar(base, vetor)
                if z > 0:
                    desenho(self._na_bola(x, y))

        self._simbolo_nave()
        self._texto(f"RUMO {round(rumo) % 360:03d}", TEXTO, centro=(BOLA_X, 12))

    def _marcador_progrado(self, centro):
        cx, cy = centro
        pygame.draw.circle(self._tela, MARCADOR, centro, 7, 2)
        pygame.draw.circle(self._tela, MARCADOR, centro, 1)
        pygame.draw.line(self._tela, MARCADOR, (cx, cy - 7), (cx, cy - 13), 2)
        pygame.draw.line(self._tela, MARCADOR, (cx - 7, cy), (cx - 13, cy), 2)
        pygame.draw.line(self._tela, MARCADOR, (cx + 7, cy), (cx + 13, cy), 2)

    def _marcador_retrogrado(self, centro):
        cx, cy = centro
        pygame.draw.circle(self._tela, MARCADOR, centro, 7, 2)
        pygame.draw.line(self._tela, MARCADOR, (cx - 4, cy - 4), (cx + 4, cy + 4), 2)
        pygame.draw.line(self._tela, MARCADOR, (cx - 4, cy + 4), (cx + 4, cy - 4), 2)
        pygame.draw.line(self._tela, MARCADOR, (cx, cy - 7), (cx, cy - 13), 2)
        pygame.draw.line(self._tela, MARCADOR, (cx - 5, cy + 5), (cx - 10, cy + 10), 2)
        pygame.draw.line(self._tela, MARCADOR, (cx + 5, cy + 5), (cx + 10, cy + 10), 2)

    def _simbolo_nave(self):
        """O "W" laranja no centro: para onde o nariz aponta. Fica sempre parado."""
        cx, cy = BOLA_X, BOLA_Y
        pygame.draw.line(self._tela, NAVE, (cx - 30, cy), (cx - 11, cy), 3)
        pygame.draw.line(self._tela, NAVE, (cx + 11, cy), (cx + 30, cy), 3)
        pygame.draw.lines(self._tela, NAVE, False, [(cx - 11, cy), (cx, cy + 9), (cx + 11, cy)], 3)
        pygame.draw.circle(self._tela, NAVE, (cx, cy - 4), 2)

    def _desenhar_numeros(self, com_sinal):
        modo = self._estados["MODO"] or "---"
        linhas = (
            ("ALT", formatar_distancia(self._numeros["ALT"])),
            (f"VEL {modo}", formatar_velocidade(self._numeros["VEL"])),
            ("AP", formatar_distancia(self._numeros["AP"])),
            ("PE", formatar_distancia(self._numeros["PE"])),
        )
        y = 4
        for rotulo, valor in linhas:
            self._texto(rotulo, ROTULO, canto=(COLUNA_X, y))
            self._texto(valor if com_sinal else "---", TEXTO, canto=(COLUNA_X, y + 14))
            y += 38

    def _desenhar_botoes(self, com_sinal, agora):
        """O botão mostra o estado do jogo, não o toque: SAS só fica verde
        quando o jogo confirma que o SAS ligou."""
        tocado, quando = self._toque
        for nome, retangulo in BOTOES.items():
            if nome == "MODO":
                cor = BOTAO_MODO
                rotulo = f"MODO {self._estados['MODO'] or '---'}"
            else:
                cor = LIGADO if com_sinal and self._estados[nome] else APAGADO
                rotulo = nome
            pygame.draw.rect(self._tela, cor, retangulo)
            if nome == tocado and agora - quando < DESTAQUE_TOQUE:
                pygame.draw.rect(self._tela, TEXTO, retangulo, 2)
            self._texto(rotulo, TEXTO, centro=retangulo.center)
