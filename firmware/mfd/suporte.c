#include <stddef.h>
#include <stdint.h>

void *memset(void *destino, int valor, size_t n)
{
    volatile uint8_t *d = destino;
    while (n--)
        *d++ = (uint8_t)valor;
    return destino;
}

void *memcpy(void *destino, const void *origem, size_t n)
{
    volatile uint8_t *d = destino;
    const volatile uint8_t *o = origem;
    while (n--)
        *d++ = *o++;
    return destino;
}

void __aeabi_memset(void *destino, size_t n, int valor)
{
    memset(destino, valor, n);
}

void __aeabi_memset4(void *destino, size_t n, int valor)
{
    memset(destino, valor, n);
}

void __aeabi_memclr(void *destino, size_t n)
{
    memset(destino, 0, n);
}

void __aeabi_memclr4(void *destino, size_t n)
{
    memset(destino, 0, n);
}

void __aeabi_memcpy(void *destino, const void *origem, size_t n)
{
    memcpy(destino, origem, n);
}

void __aeabi_memcpy4(void *destino, const void *origem, size_t n)
{
    memcpy(destino, origem, n);
}

static uint32_t dividir(uint32_t n, uint32_t d, uint32_t *resto)
{
    uint32_t q = 0;
    uint32_t r = 0;
    if (d == 0) {
        *resto = n;
        return 0xFFFFFFFFu;
    }
    for (int i = 31; i >= 0; i--) {
        r = (r << 1) | ((n >> i) & 1u);
        if (r >= d) {
            r -= d;
            q |= 1u << i;
        }
    }
    *resto = r;
    return q;
}

uint32_t __aeabi_uidiv(uint32_t n, uint32_t d)
{
    uint32_t r;
    return dividir(n, d, &r);
}

uint64_t __aeabi_uidivmod(uint32_t n, uint32_t d)
{
    uint32_t r;
    uint32_t q = dividir(n, d, &r);
    return ((uint64_t)r << 32) | q;
}

int32_t __aeabi_idiv(int32_t n, int32_t d)
{
    uint32_t r;
    uint32_t un = n < 0 ? 0u - (uint32_t)n : (uint32_t)n;
    uint32_t ud = d < 0 ? 0u - (uint32_t)d : (uint32_t)d;
    uint32_t q = dividir(un, ud, &r);
    return (n < 0) != (d < 0) ? -(int32_t)q : (int32_t)q;
}

uint64_t __aeabi_idivmod(int32_t n, int32_t d)
{
    uint32_t r;
    uint32_t un = n < 0 ? 0u - (uint32_t)n : (uint32_t)n;
    uint32_t ud = d < 0 ? 0u - (uint32_t)d : (uint32_t)d;
    uint32_t q = dividir(un, ud, &r);
    int32_t qs = (n < 0) != (d < 0) ? -(int32_t)q : (int32_t)q;
    int32_t rs = n < 0 ? -(int32_t)r : (int32_t)r;
    return ((uint64_t)(uint32_t)rs << 32) | (uint32_t)qs;
}
