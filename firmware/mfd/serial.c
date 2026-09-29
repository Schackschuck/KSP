#include <stdint.h>

#include "lpc2148.h"
#include "serial.h"

#define TAMANHO 2048u

static volatile uint8_t fila[TAMANHO];
static volatile uint32_t entrada;
static volatile uint32_t saida;

__attribute__((interrupt("IRQ"))) static void ao_receber(void)
{
    while (U0LSR & 1u) {
        uint8_t byte = (uint8_t)U0RBR;
        uint32_t proxima = (entrada + 1u) % TAMANHO;
        if (proxima != saida) {
            fila[entrada] = byte;
            entrada = proxima;
        }
    }
    VICVECTADDR = 0;
}

void serial_iniciar(void)
{
    PINSEL0 = (PINSEL0 & ~0xFu) | 0x5u;
    U0LCR = 0x83;
    U0DLL = 25;
    U0DLM = 0;
    U0FDR = (10u << 4) | 3u;
    U0LCR = 0x03;
    U0FCR = 0x07;
    VICINTSELECT &= ~(1u << VIC_UART0);
    VICVECTADDR0 = (uint32_t)ao_receber;
    VICVECTCNTL0 = 0x20u | VIC_UART0;
    VICINTENABLE = 1u << VIC_UART0;
    U0IER = 1;
}

int serial_ler(void)
{
    if (saida == entrada)
        return -1;
    int byte = fila[saida];
    saida = (saida + 1u) % TAMANHO;
    return byte;
}

void serial_descartar(void)
{
    saida = entrada;
}

void serial_enviar(const char *texto)
{
    while (*texto) {
        while (!(U0LSR & (1u << 5)))
            ;
        U0THR = (uint8_t)*texto++;
    }
}

void serial_linha(const char *texto)
{
    serial_enviar(texto);
    serial_enviar("\n");
}
