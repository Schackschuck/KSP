#ifndef DESENHO_H
#define DESENHO_H

#include <stdint.h>

#include "tabelas.h"

#define LARGURA 320
#define ALTURA 240
#define BANDA 16

#define RGB(r, g, b) ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))

enum { CANTO, CENTRO, DIREITA, MEIO_DIREITA };

extern uint16_t banda[LARGURA * BANDA];
extern int banda_y0;

void desenhar_quadro(void (*cena)(void));
int na_banda(int y0, int y1);
void ponto(int x, int y, uint16_t cor);
void faixa(int x0, int x1, int y, uint16_t cor);
void preencher(int x, int y, int largura, int altura, uint16_t cor);
void retangulo(int x, int y, int largura, int altura, uint16_t cor, int espessura, int raio);
void circulo(int cx, int cy, int raio, uint16_t cor, int espessura);
void linha(int x0, int y0, int x1, int y1, uint16_t cor, int espessura);
void linhas(const int *xy, int pontos, uint16_t cor, int espessura);
void poligono(const int *xy, int pontos, uint16_t cor, int espessura);
void elipse(int x, int y, int largura, int altura, uint16_t cor, int espessura);
int largura_texto(const char *texto, const Fonte *fonte);
void texto(const char *texto, uint16_t cor, const Fonte *fonte, int ancora, int x, int y);
uint32_t raiz(uint32_t n);
int seno10(int decimos);
int cosseno10(int decimos);

#endif
