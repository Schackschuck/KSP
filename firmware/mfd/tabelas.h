#ifndef TABELAS_H
#define TABELAS_H

#include <stdint.h>

typedef struct {
    uint8_t largura;
    uint8_t altura;
    uint8_t bytes_linha;
    const uint8_t *dados;
} Fonte;

extern const int16_t tabela_seno[901];
extern const uint8_t tabela_latitude[1025];
extern const uint16_t tabela_z[73 * 73];

extern const Fonte fonte_pequena;
extern const Fonte fonte_normal;
extern const Fonte fonte_media;
extern const Fonte fonte_grande;

#endif
