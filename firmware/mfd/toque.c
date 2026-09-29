#include <stdint.h>

#include "lpc2148.h"
#include "relogio.h"
#include "toque.h"

#define XL 25u
#define YU 28u
#define XR 29u
#define YD 30u

#define CANAL_YU 1u
#define CANAL_XR 2u
#define CANAL_YD 3u
#define CANAL_XL 4u

#define LIMIAR_TOQUE 400
#define AMOSTRAS 4

static uint32_t campo(uint32_t pino)
{
    return (pino - 16u) * 2u;
}

static void digital(uint32_t pino)
{
    PINSEL1 &= ~(3u << campo(pino));
}

static void analogico(uint32_t pino)
{
    FIO0DIR &= ~(1u << pino);
    PINSEL1 = (PINSEL1 & ~(3u << campo(pino))) | (1u << campo(pino));
}

static void saida(uint32_t pino, int nivel)
{
    digital(pino);
    if (nivel)
        FIO0SET = 1u << pino;
    else
        FIO0CLR = 1u << pino;
    FIO0DIR |= 1u << pino;
}

static void entrada(uint32_t pino)
{
    digital(pino);
    FIO0DIR &= ~(1u << pino);
}

static int converter(uint32_t canal)
{
    AD0CR = (1u << canal) | (13u << 8) | (1u << 21) | (1u << 24);
    uint32_t valor;
    do {
        valor = AD0GDR;
    } while (!(valor & 0x80000000u));
    return (int)((valor >> 6) & 0x3FFu);
}

static int media(uint32_t canal)
{
    int soma = 0;
    converter(canal);
    for (int i = 0; i < AMOSTRAS; i++)
        soma += converter(canal);
    return soma / AMOSTRAS;
}

static int apertado(void)
{
    entrada(XR);
    entrada(YU);
    saida(YD, 0);
    saida(XL, 1);
    esperar_us(20);
    analogico(XL);
    esperar_us(500);
    return converter(CANAL_XL) < LIMIAR_TOQUE;
}

void toque_iniciar(void)
{
    entrada(XR);
    entrada(YU);
    entrada(YD);
    entrada(XL);
}

int toque_ler(int *u, int *v)
{
    if (!apertado())
        return 0;

    entrada(YU);
    saida(XL, 0);
    saida(XR, 1);
    analogico(YD);
    esperar_us(200);
    int x = media(CANAL_YD);

    entrada(XL);
    saida(YD, 0);
    saida(YU, 1);
    analogico(XR);
    esperar_us(200);
    int y = media(CANAL_XR);

    int ainda = apertado();
    toque_iniciar();
    if (!ainda)
        return 0;
    *u = x;
    *v = y;
    return 1;
}
