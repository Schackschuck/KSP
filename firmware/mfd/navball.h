#ifndef NAVBALL_H
#define NAVBALL_H

#define UM 16384
#define RAIO_BOLA 72

typedef struct {
    int n, l, c;
} Vetor;

void navball_iniciar(void);
void navball_base(int pitch, int rumo, int rolagem);
void navball_direcao(int pitch, int rumo, Vetor *v);
void navball_projetar(const Vetor *v, int *x, int *y, int *z);
void navball_desenhar(int cx, int cy);

#endif
