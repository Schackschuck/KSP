"""Navball da tela multifunção: a conta que desenha a bola de atitude.

Este módulo faz, em Python, a mesma conta que o firmware da mikromedia
(LPC2148) vai fazer em C. Por isso ele evita o que é caro num ARM7 sem ponto
flutuante:

- por quadro, só 6 senos e cossenos (os três ângulos da nave);
- por ponto da bola, só multiplicações, somas e comparações, mais uma
  consulta a tabela (o arco-seno das linhas de pitch).

Aqui as contas usam numpy e números com vírgula para ficar legível; no
firmware, os mesmos passos viram inteiros em ponto fixo, ponto a ponto.

Coordenadas do mundo: (norte, leste, cima), no horizonte local da nave.
Coordenadas da bola na tela: x para a direita, y para cima e z saindo da tela
em direção a quem olha, em unidades do raio (de -1 a 1).
"""

import math

import numpy as np

# Cores (R, G, B). A tela usa 16 bits por ponto; desenhar() já arredonda.
CEU = (40, 125, 205)
CHAO = (175, 100, 40)
LINHA_CEU = (200, 225, 250)
LINHA_CHAO = (235, 200, 160)
HORIZONTE = (255, 255, 255)

PASSO_PITCH = 10              # graus entre as linhas de pitch
MEIA_LARGURA_PITCH = 0.5      # graus: meia largura de cada linha de pitch
MEIA_LARGURA_HORIZONTE = 1.2  # graus: o horizonte é mais grosso
RUMOS_MERIDIANOS = range(0, 180, 30)  # cada plano vertical dá dois meridianos: h e h + 180
MEIA_LARGURA_MERIDIANO = 0.01  # distância ao plano do meridiano, em raios
LATITUDE_MAX_MERIDIANO = 80   # graus: perto dos polos os meridianos se embolam
SOMBRA = 0.45                 # quanto a borda da bola escurece (0 = nada)


def direcao(pitch, rumo):
    """Vetor unitário (norte, leste, cima) com esse pitch e esse rumo, em graus."""
    p, r = math.radians(pitch), math.radians(rumo)
    return (math.cos(p) * math.cos(r), math.cos(p) * math.sin(r), math.sin(p))


def base_da_nave(pitch, rumo, rolagem):
    """Os três eixos da nave no mundo: (frente, direita, cima), ângulos em graus.

    A frente é para onde o nariz aponta. Sem rolagem, a direita fica na
    horizontal e o "cima" da nave fica no plano vertical que passa pelo nariz.
    A rolagem gira os dois em volta da frente. São os únicos senos e cossenos
    do quadro: no firmware, 6 consultas a uma tabela.
    """
    p, r, o = math.radians(pitch), math.radians(rumo), math.radians(rolagem)
    sp, cp = math.sin(p), math.cos(p)
    sr, cr = math.sin(r), math.cos(r)
    so, co = math.sin(o), math.cos(o)

    frente = (cp * cr, cp * sr, sp)
    direita0 = (-sr, cr, 0.0)
    cima0 = (-sp * cr, -sp * sr, cp)
    # Rolar para a direita abaixa a asa direita e inclina o "cima" para a direita.
    direita = tuple(co * d - so * c for d, c in zip(direita0, cima0))
    cima = tuple(so * d + co * c for d, c in zip(direita0, cima0))
    return frente, direita, cima


def projetar(base, v):
    """Onde o vetor v do mundo aparece na bola: (x, y, z).

    x e y vão de -1 a 1 (o raio da bola). z > 0 quer dizer que o ponto está
    na metade da bola virada para quem olha, ou seja, visível.
    """
    frente, direita, cima = base
    return (
        sum(a * b for a, b in zip(v, direita)),
        sum(a * b for a, b in zip(v, cima)),
        sum(a * b for a, b in zip(v, frente)),
    )


_grades = {}


def _grade(raio):
    """Coordenadas (x, y, z) de cada ponto da bola, que só dependem do raio.

    Calculadas uma vez só. No firmware, z = raiz(1 - x² - y²) vira uma
    tabela na flash (um quarto da bola basta, por simetria).
    """
    if raio not in _grades:
        c = (np.arange(2 * raio + 1) - raio) / raio
        x = c[np.newaxis, :]
        y = -c[:, np.newaxis]  # na imagem, a linha cresce para baixo
        r2 = x**2 + y**2
        z = np.sqrt(np.clip(1.0 - r2, 0.0, None))
        _grades[raio] = (x, y, z, r2 <= 1.0)
    return _grades[raio]


def desenhar(raio, base, fundo=(0, 0, 0)):
    """Desenha a bola vista pela nave com essa base.

    Devolve uma imagem (2*raio+1) x (2*raio+1) x 3 (linha, coluna, RGB). Fora
    do círculo fica a cor de fundo.
    """
    x, y, z, dentro = _grade(raio)
    frente, direita, cima = base

    # 1. Que direção do mundo cada ponto mostra. O centro da bola mostra
    #    para onde o nariz aponta; a borda de cima, o "cima" da nave.
    norte = x * direita[0] + y * cima[0] + z * frente[0]
    leste = x * direita[1] + y * cima[1] + z * frente[1]
    vertical = x * direita[2] + y * cima[2] + z * frente[2]

    # 2. Céu ou chão: só o sinal do componente vertical.
    ceu = (vertical >= 0)[..., np.newaxis]
    imagem = np.where(ceu, CEU, CHAO).astype(float)

    # 3. Linhas de pitch: a latitude do ponto é o arco-seno do componente
    #    vertical. No firmware, uma tabela de arco-seno.
    latitude = np.degrees(np.arcsin(np.clip(vertical, -1.0, 1.0)))
    distancia = np.abs(latitude - PASSO_PITCH * np.round(latitude / PASSO_PITCH))
    linha = distancia < MEIA_LARGURA_PITCH

    # 4. Meridianos: o meridiano do rumo h está no plano vertical que contém
    #    esse rumo. A distância de um ponto ao plano é um produto escalar com
    #    a normal do plano: duas multiplicações, sem arco-tangente.
    perto_do_polo = np.abs(latitude) > LATITUDE_MAX_MERIDIANO
    for h in RUMOS_MERIDIANOS:
        normal_norte, normal_leste = -math.sin(math.radians(h)), math.cos(math.radians(h))
        plano = np.abs(normal_norte * norte + normal_leste * leste)
        linha |= (plano < MEIA_LARGURA_MERIDIANO) & ~perto_do_polo

    imagem = np.where(linha[..., np.newaxis], np.where(ceu, LINHA_CEU, LINHA_CHAO), imagem)
    horizonte = np.abs(latitude) < MEIA_LARGURA_HORIZONTE
    imagem = np.where(horizonte[..., np.newaxis], HORIZONTE, imagem)

    # 5. Sombra: a borda escurece, o que dá a impressão de esfera.
    imagem *= (1.0 - SOMBRA + SOMBRA * z)[..., np.newaxis]

    imagem = np.where(dentro[..., np.newaxis], imagem, fundo).astype(np.uint8)
    # 16 bits por ponto (RGB565): 5 bits de vermelho, 6 de verde e 5 de azul.
    # Zerar os bits que a tela não tem mostra aqui as cores que ela vai mostrar.
    return imagem & np.array([0xF8, 0xFC, 0xF8], dtype=np.uint8)
