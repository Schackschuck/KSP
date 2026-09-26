"""Simulador da tela multifunção (mikromedia for ARM, 320x240 com touch).

Faz no PC o papel do firmware da mikromedia: recebe as mensagens do protocolo
(ATT, ALT, SAS...) como se tivessem chegado pela serial, desenha a tela e,
quando alguém toca num botão, responde TOQUE <nome>. O mfd.py conversa com
ele exatamente como vai conversar com a placa: enviar() e linhas(), igual à
classe Painel da ponte.

O desenho daqui é a referência do firmware: as posições, os tamanhos e as
cores são os que a placa vai usar. A janela só aumenta os pontos (--zoom),
sem suavizar, para parecer com a tela de verdade.

Layout, inspirado na navball do KSP2:

    ACEL            [ 269 ]             V VERT
     |         240 ' ' O ' ' 300          | +100
     |          .-----------.             |  +10
     |        .'    navball  '.           |
     | [VEL ORB ]     -W-     [ ALT     ] |
     | [2287 m/s]             [ 84321 m ] |  -10
     |        '.             .'           | -100
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

BOLA_X, BOLA_Y, BOLA_RAIO = 160, 104, 64
ARO_RAIO = 78           # o aro escuro em volta da bola, onde fica a fita de rumo
FITA_ALCANCE = 60       # graus de rumo mostrados para cada lado do atual

CAIXA_RUMO = pygame.Rect(141, 2, 38, 18)
CAIXA_VEL = pygame.Rect(22, 90, 80, 32)      # tocar nela troca o modo
CAIXA_ALT = pygame.Rect(218, 90, 80, 32)

# Barras verticais nas bordas. Na placa, preencher um retângulo é muito mais
# rápido que desenhar um arco ponto a ponto.
BARRA_ACEL = pygame.Rect(6, 30, 10, 156)
BARRA_VV = pygame.Rect(304, 30, 10, 156)
VV_MAX = 1000           # m/s no fim da barra; a escala é logarítmica

PAINEL = pygame.Rect(48, 198, 224, 40)       # informações do modo, embaixo

BOTOES_REDONDOS = {"RCS": (140, 178), "SAS": (180, 178)}
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
TRACO_FITA = rgb565(110, 140, 210)
CARDEAL_FITA = rgb565(255, 90, 80)
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
CARDEAL = rgb565(255, 255, 255)
TRANSPARENTE = rgb565(255, 0, 255)  # fora do círculo da bola; não é desenhado

# Marcadores, com as cores do KSP.
COR_PRO = rgb565(230, 210, 40)
COR_NRM = rgb565(200, 70, 255)
COR_RDL = rgb565(60, 210, 230)
COR_TGT = rgb565(255, 140, 200)
COR_MNV = rgb565(60, 130, 255)

# Pontos cardeais: L = leste, O = oeste.
CARDEAIS = (("N", 0), ("L", 90), ("S", 180), ("O", 270))

# Marcadores que dependem do modo e números que só existem em alguns modos:
# a tela os apaga quando o modo muda.
MARCADORES_DO_MODO = ("PRO", "NRM", "RDL")
NUMEROS_DO_MODO = ("VEL", "VH", "AP", "PE", "TAP", "TPE", "DIST")
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


def _polar(raio, angulo):
    """Ponto da tela a esse raio do centro da bola; ângulo em graus, 0 à direita, 90 em cima."""
    a = math.radians(angulo)
    return (BOLA_X + raio * math.cos(a), BOLA_Y - raio * math.sin(a))


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

        # O que a tela sabe, só a partir das mensagens. None = ainda não chegou.
        self._atitude = None       # (pitch, rumo, rolagem) em graus
        self._marcadores = dict.fromkeys(("PRO", "NRM", "RDL", "TGT", "MNV"))  # (pitch, rumo)
        self._altitude = None      # ("ALT" ou "RAD", metros)
        self._numeros = dict.fromkeys(NUMEROS_DO_MODO + ("VV", "ACEL"))
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
        self._desenhar_aro(com_sinal)
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

    def _desenhar_aro(self, com_sinal):
        """O aro com a fita de rumo em cima, e a caixa com o rumo atual."""
        pygame.draw.circle(self._tela, ARO, (BOLA_X, BOLA_Y), ARO_RAIO)
        pygame.draw.circle(self._tela, BORDA, (BOLA_X, BOLA_Y), ARO_RAIO, 1)

        if com_sinal and self._atitude is not None:
            rumo = self._atitude[1]
            pequena = self._fonte_pequena
            # Um traço a cada 10°; a cada 30°, o número no lugar do traço.
            # Rumo maior fica à direita, como na bússola de um avião.
            primeiro = math.ceil((rumo - FITA_ALCANCE) / 10) * 10
            for marca in range(primeiro, int(rumo + FITA_ALCANCE) + 1, 10):
                angulo = 90 - (marca - rumo)
                if marca % 30:
                    pygame.draw.line(self._tela, TRACO_FITA, _polar(66, angulo), _polar(71, angulo), 1)
                    continue
                marca %= 360
                letra = dict((h, n) for n, h in CARDEAIS).get(marca)
                rotulo, cor = (letra, CARDEAL_FITA) if letra else (f"{marca:03d}", TRACO_FITA)
                self._texto(rotulo, cor, centro=_polar(71, angulo), fonte=pequena)
            texto_rumo = f"{round(rumo) % 360:03d}"
        else:
            texto_rumo = "---"

        pygame.draw.polygon(self._tela, TEXTO, [(BOLA_X - 4, 21), (BOLA_X + 4, 21), (BOLA_X, 27)])
        pygame.draw.rect(self._tela, FUNDO, CAIXA_RUMO, border_radius=3)
        pygame.draw.rect(self._tela, TEXTO, CAIXA_RUMO, 1, border_radius=3)
        self._texto(texto_rumo, TEXTO, centro=CAIXA_RUMO.center)

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

        for letra, rumo_cardeal in CARDEAIS:
            x, y, z = navball.projetar(base, navball.direcao(5, rumo_cardeal))
            if z > 0.3:  # perto da borda a letra ficaria em cima do aro
                self._texto(letra, CARDEAL, centro=self._na_bola(x, y), fonte=self._fonte_pequena)

        # Cada marcador tem um par do lado oposto da bola (menos a manobra).
        # Um marcador só aparece se estiver na metade visível da bola. A
        # ordem é a de desenho: o último fica por cima.
        pares = (
            ("RDL", self._radial_fora, self._radial_dentro),
            ("NRM", self._normal, self._antinormal),
            ("TGT", self._alvo, self._antialvo),
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

    def _simbolo_nave(self):
        """O "W" laranja no centro: para onde o nariz aponta. Fica sempre parado."""
        cx, cy = BOLA_X, BOLA_Y
        pygame.draw.line(self._tela, NAVE, (cx - 24, cy), (cx - 9, cy), 3)
        pygame.draw.line(self._tela, NAVE, (cx + 9, cy), (cx + 24, cy), 3)
        pygame.draw.lines(self._tela, NAVE, False, [(cx - 9, cy), (cx, cy + 7), (cx + 9, cy)], 3)
        pygame.draw.circle(self._tela, NAVE, (cx, cy - 3), 2)

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
            pygame.draw.line(self._tela, TRACO_FITA, (b.x - 3, y), (b.x, y), 1)
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
        """Embaixo: o que interessa em cada modo."""
        n = self._numeros
        modo = self._estados["MODO"]
        if not com_sinal:
            linhas = []
        elif modo == "SUP":
            linhas = [
                ("V VERT", formatar_velocidade(n["VV"]), ""),
                ("V HOR", formatar_velocidade(n["VH"]), ""),
            ]
        elif modo == "ORB":
            linhas = [
                ("AP", formatar_distancia(n["AP"]), formatar_tempo(n["TAP"])),
                ("PE", formatar_distancia(n["PE"]), formatar_tempo(n["TPE"])),
            ]
        elif modo == "ALVO":
            linhas = [("DIST", formatar_distancia(n["DIST"]), "")]
        else:
            linhas = []

        pygame.draw.rect(self._tela, BORDA, PAINEL, 1, border_radius=4)
        y = PAINEL.y + 3
        for rotulo, valor, tempo in linhas:
            self._texto(rotulo, ROTULO, canto=(PAINEL.x + 6, y + 2), fonte=self._fonte_pequena)
            self._texto(valor, TEXTO, direita=(PAINEL.x + 128, y))
            if tempo:
                self._texto(tempo, ROTULO, direita=(PAINEL.right - 5, y + 2), fonte=self._fonte_pequena)
            y += 17
