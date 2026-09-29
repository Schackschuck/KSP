#ifndef RELOGIO_H
#define RELOGIO_H

#include <stdint.h>

void relogio_iniciar(void);
uint32_t relogio_us(void);
uint32_t relogio_ms(void);
void esperar_us(uint32_t us);
void esperar_ms(uint32_t ms);

#endif
