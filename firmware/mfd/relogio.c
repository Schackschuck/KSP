#include "relogio.h"
#include "lpc2148.h"

static uint32_t ultimo;
static uint32_t resto;
static uint32_t milissegundos;

static void iniciar_pll(void)
{
    PLL0CFG = 0x24;
    PLL0CON = 1;
    PLL0FEED = 0xAA;
    PLL0FEED = 0x55;
    while (!(PLL0STAT & (1u << 10)))
        ;
    PLL0CON = 3;
    PLL0FEED = 0xAA;
    PLL0FEED = 0x55;
    MAMCR = 0;
    MAMTIM = 3;
    MAMCR = 2;
    VPBDIV = 1;
}

void relogio_iniciar(void)
{
    iniciar_pll();
    T0TCR = 2;
    T0PR = CCLK_KHZ / 1000 - 1;
    T0TCR = 1;
    ultimo = T0TC;
}

uint32_t relogio_us(void)
{
    return T0TC;
}

uint32_t relogio_ms(void)
{
    uint32_t agora = T0TC;
    resto += agora - ultimo;
    ultimo = agora;
    milissegundos += resto / 1000;
    resto %= 1000;
    return milissegundos;
}

void esperar_us(uint32_t us)
{
    uint32_t inicio = T0TC;
    while (T0TC - inicio < us)
        ;
}

void esperar_ms(uint32_t ms)
{
    while (ms--)
        esperar_us(1000);
}
