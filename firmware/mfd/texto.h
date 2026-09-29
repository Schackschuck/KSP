#ifndef TEXTO_H
#define TEXTO_H

#include <stdint.h>

int igual(const char *a, const char *b);
int ler_inteiro(const char *texto, int32_t *valor);
char *escrever_inteiro(char *destino, int32_t valor, int digitos);
char *escrever_texto(char *destino, const char *texto);
char *escrever_decimal(char *destino, int32_t valor, int divisor, int casas);
char *escrever_hex(char *destino, uint32_t valor, int digitos);
void formatar_distancia(char *destino, int valido, int32_t metros);
void formatar_velocidade(char *destino, int valido, int32_t decimos);
void formatar_tempo(char *destino, int valido, int32_t segundos);
int32_t log2q(uint32_t valor);

#endif
