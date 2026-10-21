#ifndef CENA_H
#define CENA_H

#include <stdint.h>

enum { CENA_PAD, CENA_TRAJ, CENA_ORB, CENA_MANTER };
enum { CORPO_KERBIN, CORPO_MUN, CORPO_MINMUS, CORPO_OUTRO };

typedef struct {
    int32_t raio, topo, alvo, alt, ap, pe;
    int ap_ok, pe_ok;
    int anom;
    int modo, corpo, motor;
} DadosCena;

#define CENA_TOPO 70
#define CENA_FUNDO 190

void cena_esquecer(void);
void cena_desenhar(const DadosCena *d, uint32_t agora);

#endif
