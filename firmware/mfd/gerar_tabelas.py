"""Gera tabelas.c: as fontes e as tabelas de conta do firmware da tela.

O firmware roda num ARM7 sem ponto flutuante, então o que é caro (seno,
arco-seno, raiz e o desenho das letras) vira tabela na flash, calculada aqui.
As fontes saem da mesma família monoespaçada do simulador, nos mesmos tamanhos,
sem suavização, porque a tela só acende ou apaga cada ponto de uma letra.

Uso, a partir desta pasta (precisa do pygame, o mesmo do simulador):
    python gerar_tabelas.py
    python gerar_tabelas.py --fonte C:\\Windows\\Fonts\\consola.ttf
"""

import argparse
import math
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE_PADRAO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
TAMANHOS = {"pequena": 11, "normal": 14, "media": 16, "grande": 20}
PRIMEIRO, ULTIMO = 32, 126
RAIO_BOLA = 72
UM = 1 << 14
PASSO_PITCH = 10
MEIA_LARGURA_PITCH = 0.5
MEIA_LARGURA_HORIZONTE = 1.2
LATITUDE_MAX_MERIDIANO = 80
ENTRADAS_ASIN = 1025


def lista(valores, por_linha=16):
    valores = [str(v) for v in valores]
    return ",\n".join("    " + ", ".join(valores[i:i + por_linha]) for i in range(0, len(valores), por_linha))


def seno():
    return [round(math.sin(math.radians(d / 10)) * UM) for d in range(901)]


def classes_de_latitude():
    """Para cada componente vertical, de -1 a 1: linha de pitch, horizonte e perto do polo."""
    classes = []
    for i in range(ENTRADAS_ASIN):
        vertical = max(-1.0, min(1.0, (i * 32 - UM) / UM))
        latitude = math.degrees(math.asin(vertical))
        distancia = abs(latitude - PASSO_PITCH * round(latitude / PASSO_PITCH))
        classe = 0
        if distancia < MEIA_LARGURA_PITCH:
            classe |= 1
        if abs(latitude) < MEIA_LARGURA_HORIZONTE:
            classe |= 2
        if abs(latitude) > LATITUDE_MAX_MERIDIANO:
            classe |= 4
        classes.append(classe)
    return classes


def profundidade():
    """z = raiz(1 - x² - y²) de um quarto da bola, em ponto fixo; 0 fora dela."""
    valores = []
    for j in range(RAIO_BOLA + 1):
        for i in range(RAIO_BOLA + 1):
            r2 = (i * i + j * j) / (RAIO_BOLA * RAIO_BOLA)
            valores.append(round(math.sqrt(1.0 - r2) * UM) if r2 <= 1.0 else 0)
    return valores


def fonte(caminho, tamanho):
    letra = pygame.font.Font(caminho, tamanho)
    texto = "".join(chr(c) for c in range(PRIMEIRO, ULTIMO + 1))
    largura = letra.size(texto)[0] // len(texto)
    altura = letra.get_height()
    bytes_linha = (largura + 7) // 8
    dados = []
    for c in texto:
        imagem = letra.render(c, False, (255, 255, 255), (0, 0, 0))
        for y in range(altura):
            bits = 0
            for x in range(bytes_linha * 8):
                aceso = x < largura and x < imagem.get_width() and y < imagem.get_height() and imagem.get_at((x, y))[0] > 127
                bits = (bits << 1) | int(aceso)
            dados.extend((bits >> (8 * k)) & 0xFF for k in reversed(range(bytes_linha)))
    return largura, altura, bytes_linha, dados


def main():
    parser = argparse.ArgumentParser(description="Gera tabelas.c do firmware da tela multifunção.")
    parser.add_argument("--fonte", default=FONTE_PADRAO, help="arquivo .ttf de uma fonte monoespaçada")
    args = parser.parse_args()
    pygame.font.init()

    partes = ['#include "tabelas.h"', ""]
    partes.append(f"const int16_t tabela_seno[901] = {{\n{lista(seno())}\n}};\n")
    partes.append(f"const uint8_t tabela_latitude[{ENTRADAS_ASIN}] = {{\n{lista(classes_de_latitude(), 32)}\n}};\n")
    lado = RAIO_BOLA + 1
    partes.append(f"const uint16_t tabela_z[{lado * lado}] = {{\n{lista(profundidade())}\n}};\n")
    for nome, tamanho in TAMANHOS.items():
        largura, altura, bytes_linha, dados = fonte(args.fonte, tamanho)
        partes.append(f"static const uint8_t dados_{nome}[{len(dados)}] = {{\n{lista(dados, 24)}\n}};\n")
        partes.append(f"const Fonte fonte_{nome} = {{{largura}, {altura}, {bytes_linha}, dados_{nome}}};\n")

    with open(os.path.join(AQUI, "tabelas.c"), "w", encoding="ascii", newline="\n") as saida:
        saida.write("\n".join(partes))
    print("tabelas.c gerado.")


if __name__ == "__main__":
    main()
