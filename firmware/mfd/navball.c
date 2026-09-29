#include "navball.h"
#include "desenho.h"
#include "tabelas.h"

#define NIVEIS 65
#define LIMIAR_MERIDIANO 164
#define COS30 14189

enum { COR_CEU, COR_CHAO, COR_LINHA_CEU, COR_LINHA_CHAO, COR_HORIZONTE, CORES };

static const uint8_t cores[CORES][3] = {
    {40, 105, 200},
    {150, 70, 25},
    {150, 195, 250},
    {250, 150, 60},
    {255, 255, 255},
};

static uint16_t sombra[CORES][NIVEIS];
static int eixo[2 * RAIO_BOLA + 1];
static Vetor frente, direita, cima;

void navball_iniciar(void)
{
    for (int k = 0; k <= 2 * RAIO_BOLA; k++) {
        int i = k - RAIO_BOLA;
        eixo[k] = (i * UM + (i >= 0 ? RAIO_BOLA / 2 : -RAIO_BOLA / 2)) / RAIO_BOLA;
    }
    for (int c = 0; c < CORES; c++) {
        for (int n = 0; n < NIVEIS; n++) {
            int fator = 9011 + 7373 * n / 64;
            int r = cores[c][0] * fator >> 14;
            int g = cores[c][1] * fator >> 14;
            int b = cores[c][2] * fator >> 14;
            sombra[c][n] = RGB(r, g, b);
        }
    }
    navball_base(0, 0, 0);
}

void navball_base(int pitch, int rumo, int rolagem)
{
    int sp = seno10(pitch), cp = cosseno10(pitch);
    int sr = seno10(rumo), cr = cosseno10(rumo);
    int so = seno10(rolagem), co = cosseno10(rolagem);

    frente.n = cp * cr >> 14;
    frente.l = cp * sr >> 14;
    frente.c = sp;

    Vetor d0 = {-sr, cr, 0};
    Vetor c0 = {-(sp * cr >> 14), -(sp * sr >> 14), cp};
    direita.n = (co * d0.n - so * c0.n) >> 14;
    direita.l = (co * d0.l - so * c0.l) >> 14;
    direita.c = (co * d0.c - so * c0.c) >> 14;
    cima.n = (so * d0.n + co * c0.n) >> 14;
    cima.l = (so * d0.l + co * c0.l) >> 14;
    cima.c = (so * d0.c + co * c0.c) >> 14;
}

void navball_direcao(int pitch, int rumo, Vetor *v)
{
    int cp = cosseno10(pitch);
    v->n = cp * cosseno10(rumo) >> 14;
    v->l = cp * seno10(rumo) >> 14;
    v->c = seno10(pitch);
}

static int escalar(const Vetor *a, const Vetor *b)
{
    return (a->n * b->n + a->l * b->l + a->c * b->c) >> 14;
}

void navball_projetar(const Vetor *v, int *x, int *y, int *z)
{
    *x = escalar(v, &direita);
    *y = escalar(v, &cima);
    *z = escalar(v, &frente);
}

static inline int modulo(int v)
{
    return v < 0 ? -v : v;
}

void navball_desenhar(int cx, int cy)
{
    int y0 = cy - RAIO_BOLA > banda_y0 ? cy - RAIO_BOLA : banda_y0;
    int y1 = cy + RAIO_BOLA < banda_y0 + BANDA - 1 ? cy + RAIO_BOLA : banda_y0 + BANDA - 1;
    for (int yy = y0; yy <= y1; yy++) {
        int j = yy - cy;
        int aj = modulo(j);
        int yq = -eixo[j + RAIO_BOLA];
        int linha_n = yq * cima.n;
        int linha_l = yq * cima.l;
        int linha_v = yq * cima.c;
        int meia = (int)raiz((uint32_t)(RAIO_BOLA * RAIO_BOLA - j * j));
        const uint16_t *zs = &tabela_z[aj * (RAIO_BOLA + 1)];
        uint16_t *p = &banda[(yy - banda_y0) * LARGURA + cx - meia];
        for (int i = -meia; i <= meia; i++) {
            int xq = eixo[i + RAIO_BOLA];
            int zq = zs[modulo(i)];
            int norte = (xq * direita.n + linha_n + zq * frente.n) >> 14;
            int leste = (xq * direita.l + linha_l + zq * frente.l) >> 14;
            int vertical = (xq * direita.c + linha_v + zq * frente.c) >> 14;
            int indice = (vertical + UM) >> 5;
            if (indice < 0)
                indice = 0;
            if (indice > 1024)
                indice = 1024;
            int classe = tabela_latitude[indice];
            int ceu = vertical >= 0;
            int risco = classe & 1;
            if (!risco && !(classe & 4)) {
                int n30 = norte * COS30 >> 14;
                int l30 = leste * COS30 >> 14;
                int nm = norte >> 1;
                int lm = leste >> 1;
                risco = modulo(leste) < LIMIAR_MERIDIANO || modulo(norte) < LIMIAR_MERIDIANO ||
                        modulo(l30 - nm) < LIMIAR_MERIDIANO || modulo(lm - n30) < LIMIAR_MERIDIANO ||
                        modulo(n30 + lm) < LIMIAR_MERIDIANO || modulo(nm + l30) < LIMIAR_MERIDIANO;
            }
            int cor;
            if (classe & 2)
                cor = COR_HORIZONTE;
            else if (risco)
                cor = ceu ? COR_LINHA_CEU : COR_LINHA_CHAO;
            else
                cor = ceu ? COR_CEU : COR_CHAO;
            *p++ = sombra[cor][zq >> 8];
        }
    }
}
