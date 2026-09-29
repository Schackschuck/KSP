#include "texto.h"

int igual(const char *a, const char *b)
{
    while (*a && *a == *b) {
        a++;
        b++;
    }
    return *a == *b;
}

int ler_inteiro(const char *texto, int32_t *valor)
{
    int negativo = 0;
    if (*texto == '+' || *texto == '-') {
        negativo = *texto == '-';
        texto++;
    }
    if (!*texto)
        return 0;
    uint32_t total = 0;
    for (; *texto; texto++) {
        if (*texto < '0' || *texto > '9')
            return 0;
        uint32_t proximo = total * 10u + (uint32_t)(*texto - '0');
        if (proximo > 0x7FFFFFFFu || proximo < total)
            return 0;
        total = proximo;
    }
    *valor = negativo ? -(int32_t)total : (int32_t)total;
    return 1;
}

char *escrever_texto(char *destino, const char *texto)
{
    while (*texto)
        *destino++ = *texto++;
    *destino = 0;
    return destino;
}

static char *escrever_natural(char *destino, uint32_t valor, int digitos)
{
    char reverso[12];
    int n = 0;
    do {
        reverso[n++] = (char)('0' + valor % 10u);
        valor /= 10u;
    } while (valor);
    while (n < digitos && n < 11)
        reverso[n++] = '0';
    while (n)
        *destino++ = reverso[--n];
    *destino = 0;
    return destino;
}

char *escrever_inteiro(char *destino, int32_t valor, int digitos)
{
    if (valor < 0) {
        *destino++ = '-';
        return escrever_natural(destino, 0u - (uint32_t)valor, digitos);
    }
    return escrever_natural(destino, (uint32_t)valor, digitos);
}

char *escrever_decimal(char *destino, int32_t valor, int divisor, int casas)
{
    uint32_t escala = 1;
    for (int i = 0; i < casas; i++)
        escala *= 10u;
    uint32_t a = valor < 0 ? 0u - (uint32_t)valor : (uint32_t)valor;
    uint32_t inteira = a / (uint32_t)divisor;
    uint32_t resto = a % (uint32_t)divisor;
    uint32_t fracao = (resto * escala * 2u + (uint32_t)divisor) / (2u * (uint32_t)divisor);
    if (fracao >= escala) {
        inteira++;
        fracao -= escala;
    }
    if (valor < 0)
        *destino++ = '-';
    destino = escrever_natural(destino, inteira, 1);
    if (casas > 0) {
        *destino++ = '.';
        destino = escrever_natural(destino, fracao, casas);
    }
    return destino;
}

char *escrever_hex(char *destino, uint32_t valor, int digitos)
{
    for (int i = digitos - 1; i >= 0; i--)
        *destino++ = "0123456789ABCDEF"[(valor >> (4 * i)) & 0xFu];
    *destino = 0;
    return destino;
}

void formatar_distancia(char *destino, int valido, int32_t metros)
{
    if (!valido) {
        escrever_texto(destino, "---");
        return;
    }
    int32_t a = metros < 0 ? -metros : metros;
    if (a < 100000) {
        destino = escrever_inteiro(destino, metros, 1);
        escrever_texto(destino, " m");
    } else if (a < 10000000) {
        destino = escrever_decimal(destino, metros, 1000, 1);
        escrever_texto(destino, " km");
    } else if (a < 1000000000) {
        destino = escrever_decimal(destino, metros, 1000, 0);
        escrever_texto(destino, " km");
    } else {
        destino = escrever_decimal(destino, metros, 1000000, 0);
        escrever_texto(destino, " Mm");
    }
}

void formatar_velocidade(char *destino, int valido, int32_t decimos)
{
    if (!valido) {
        escrever_texto(destino, "---");
        return;
    }
    if (decimos < 0) {
        *destino++ = '-';
        decimos = -decimos;
    }
    destino = escrever_inteiro(destino, decimos / 10, 1);
    if (decimos < 10000) {
        *destino++ = '.';
        destino = escrever_inteiro(destino, decimos % 10, 1);
    }
    escrever_texto(destino, " m/s");
}

void formatar_tempo(char *destino, int valido, int32_t segundos)
{
    if (!valido) {
        escrever_texto(destino, "T- ---");
        return;
    }
    if (segundos < 0)
        segundos = 0;
    int32_t horas = segundos / 3600;
    int32_t resto = segundos % 3600;
    destino = escrever_texto(destino, "T-");
    if (horas >= 100) {
        destino = escrever_inteiro(destino, horas, 1);
        escrever_texto(destino, "h");
        return;
    }
    destino = escrever_inteiro(destino, horas, 2);
    *destino++ = ':';
    destino = escrever_inteiro(destino, resto / 60, 2);
    *destino++ = ':';
    escrever_inteiro(destino, resto % 60, 2);
}

int32_t log2q(uint32_t valor)
{
    if (valor == 0)
        return 0;
    int n = 31;
    while (!(valor & (1u << n)))
        n--;
    uint32_t x = n >= 30 ? valor >> (n - 30) : valor << (30 - n);
    int32_t fracao = 0;
    for (int i = 15; i >= 0; i--) {
        x = (uint32_t)(((uint64_t)x * x) >> 30);
        if (x >= 0x80000000u) {
            x >>= 1;
            fracao |= 1 << i;
        }
    }
    return (n << 16) | fracao;
}
