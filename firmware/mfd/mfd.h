#ifndef MFD_H
#define MFD_H

#include <stdint.h>

void mfd_iniciar(void);
void mfd_receber(int byte, uint32_t agora);
void mfd_tocar(int x, int y, uint32_t agora);
void mfd_desenhar(uint32_t agora);

#endif
