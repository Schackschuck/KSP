#include "lcd.h"
#include "lpc2148.h"
#include "relogio.h"

#define RS (1u << 8)
#define RD (1u << 9)
#define CS (1u << 10)
#define RST (1u << 11)
#define WR (1u << 12)
#define LUZ (1u << 13)
#define DADOS0 (0xFFu << 15)
#define DADOS1 (0xFFu << 16)

static uint16_t id;

static inline void escrever(uint16_t valor)
{
    FIO1PIN = ((uint32_t)valor & 0xFF00u) << 8;
    FIO0CLR = DADOS0;
    FIO0SET = ((uint32_t)valor & 0xFFu) << 15;
    FIO0CLR = WR;
    __asm__ volatile("nop");
    FIO0SET = WR;
}

static void indice(uint8_t registrador)
{
    FIO0CLR = RS;
    escrever(registrador);
    FIO0SET = RS;
}

static void registro(uint8_t registrador, uint16_t valor)
{
    indice(registrador);
    escrever(valor);
}

static uint16_t ler_registro(uint8_t registrador)
{
    indice(registrador);
    FIO0DIR &= ~DADOS0;
    FIO1DIR &= ~DADOS1;
    FIO0CLR = RD;
    esperar_us(2);
    uint16_t valor = (uint16_t)((((FIO1PIN >> 16) & 0xFFu) << 8) | ((FIO0PIN >> 15) & 0xFFu));
    FIO0SET = RD;
    FIO0DIR |= DADOS0;
    FIO1DIR |= DADOS1;
    return valor;
}

static void iniciar_pinos(void)
{
    PINSEL0 &= 0x0000FFFFu;
    PINSEL1 &= ~0x3FFFu;
    PINSEL2 &= ~(1u << 3);
    SCS |= 3u;
    FIO1MASK = ~DADOS1;
    FIO0SET = RS | RD | CS | RST | WR;
    FIO0CLR = LUZ;
    FIO0DIR |= RS | RD | CS | RST | WR | LUZ | DADOS0;
    FIO1DIR |= DADOS1;
}

typedef struct {
    uint8_t registrador;
    uint8_t valor;
} Passo;

#define PAUSA 0xFF

static void executar(const Passo *passos, int quantos)
{
    for (int i = 0; i < quantos; i++) {
        if (passos[i].registrador == PAUSA)
            esperar_ms(passos[i].valor);
        else
            registro(passos[i].registrador, passos[i].valor);
    }
}

static void iniciar_hx8347d(void)
{
    static const Passo passos[] = {
        {0xEA, 0x00}, {0xEB, 0x20}, {0xEC, 0x0C}, {0xED, 0xC4}, {0xE8, 0x40}, {0xE9, 0x38},
        {0xF1, 0x01}, {0xF2, 0x10}, {0x27, 0xA3},
        {0x1B, 0x1B}, {0x1A, 0x01}, {0x24, 0x2F}, {0x25, 0x57}, {0x23, 0x8D},
        {0x18, 0x36}, {0x19, 0x01}, {0x01, 0x00},
        {0x1F, 0x88}, {PAUSA, 5}, {0x1F, 0x80}, {PAUSA, 5}, {0x1F, 0x90}, {PAUSA, 5}, {0x1F, 0xD0}, {PAUSA, 5},
        {0x17, 0x05}, {0x36, 0x00}, {0x28, 0x38}, {PAUSA, 40}, {0x28, 0x3C},
    };
    executar(passos, sizeof(passos) / sizeof(passos[0]));
}

static void iniciar_hx8347g(void)
{
    static const Passo passos[] = {
        {0x2E, 0x89}, {0x29, 0x8F}, {0x2B, 0x02}, {0xE2, 0x00}, {0xE4, 0x01}, {0xE5, 0x10},
        {0xE6, 0x01}, {0xE7, 0x10}, {0xE8, 0x70}, {0xF2, 0x00}, {0xEA, 0x00}, {0xEB, 0x20},
        {0xEC, 0x3C}, {0xED, 0xC8}, {0xE9, 0x38}, {0xF1, 0x01},
        {0x1B, 0x1A}, {0x1A, 0x02}, {0x24, 0x61}, {0x25, 0x5C},
        {0x18, 0x36}, {0x19, 0x01}, {0x01, 0x00},
        {0x1F, 0x88}, {PAUSA, 5}, {0x1F, 0x80}, {PAUSA, 5}, {0x1F, 0x90}, {PAUSA, 5}, {0x1F, 0xD4}, {PAUSA, 5},
        {0x17, 0x05}, {0x36, 0x00}, {0x28, 0x38}, {PAUSA, 40}, {0x28, 0x3C},
    };
    executar(passos, sizeof(passos) / sizeof(passos[0]));
}

void lcd_iniciar(void)
{
    iniciar_pinos();
    esperar_ms(5);
    FIO0CLR = RST;
    esperar_ms(10);
    FIO0SET = RST;
    esperar_ms(120);
    FIO0CLR = CS;

    id = ler_registro(0x00);
    if ((id & 0xFF) == 0x75)
        iniciar_hx8347g();
    else
        iniciar_hx8347d();
    registro(0x16, 0x68);
}

uint16_t lcd_id(void)
{
    return id;
}

void lcd_orientacao(uint8_t valor)
{
    registro(0x16, valor);
}

void lcd_luz(int ligada)
{
    if (ligada)
        FIO0SET = LUZ;
    else
        FIO0CLR = LUZ;
}

void lcd_janela(int x0, int y0, int x1, int y1)
{
    registro(0x02, (uint16_t)(x0 >> 8));
    registro(0x03, (uint16_t)(x0 & 0xFF));
    registro(0x04, (uint16_t)(x1 >> 8));
    registro(0x05, (uint16_t)(x1 & 0xFF));
    registro(0x06, (uint16_t)(y0 >> 8));
    registro(0x07, (uint16_t)(y0 & 0xFF));
    registro(0x08, (uint16_t)(y1 >> 8));
    registro(0x09, (uint16_t)(y1 & 0xFF));
    indice(0x22);
}

void lcd_pixels(const uint16_t *pixels, int quantos)
{
    while (quantos--)
        escrever(*pixels++);
}

void lcd_preencher(uint16_t cor, int quantos)
{
    while (quantos--)
        escrever(cor);
}
