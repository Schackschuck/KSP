#include "desenho.h"
#include "lcd.h"

uint16_t banda[LARGURA * BANDA];
int banda_y0;

void desenhar_quadro(void (*cena)(void))
{
    for (banda_y0 = 0; banda_y0 < ALTURA; banda_y0 += BANDA) {
        cena();
        lcd_janela(0, banda_y0, LARGURA - 1, banda_y0 + BANDA - 1);
        lcd_pixels(banda, LARGURA * BANDA);
    }
}

int na_banda(int y0, int y1)
{
    return y1 >= banda_y0 && y0 < banda_y0 + BANDA;
}

uint32_t raiz(uint32_t n)
{
    uint32_t r = 0;
    uint32_t bit = 1u << 30;
    while (bit > n)
        bit >>= 2;
    while (bit) {
        if (n >= r + bit) {
            n -= r + bit;
            r = (r >> 1) + bit;
        } else {
            r >>= 1;
        }
        bit >>= 2;
    }
    return r;
}

int seno10(int decimos)
{
    decimos %= 3600;
    if (decimos < 0)
        decimos += 3600;
    if (decimos <= 900)
        return tabela_seno[decimos];
    if (decimos <= 1800)
        return tabela_seno[1800 - decimos];
    if (decimos <= 2700)
        return -tabela_seno[decimos - 1800];
    return -tabela_seno[3600 - decimos];
}

int cosseno10(int decimos)
{
    return seno10(decimos + 900);
}

void ponto(int x, int y, uint16_t cor)
{
    int yb = y - banda_y0;
    if ((unsigned)x < LARGURA && (unsigned)yb < BANDA)
        banda[yb * LARGURA + x] = cor;
}

void faixa(int x0, int x1, int y, uint16_t cor)
{
    int yb = y - banda_y0;
    if ((unsigned)yb >= BANDA)
        return;
    if (x0 < 0)
        x0 = 0;
    if (x1 > LARGURA - 1)
        x1 = LARGURA - 1;
    uint16_t *p = &banda[yb * LARGURA + x0];
    for (int x = x0; x <= x1; x++)
        *p++ = cor;
}

void preencher(int x, int y, int largura, int altura, uint16_t cor)
{
    int y0 = y > banda_y0 ? y : banda_y0;
    int y1 = y + altura - 1;
    if (y1 > banda_y0 + BANDA - 1)
        y1 = banda_y0 + BANDA - 1;
    for (int yy = y0; yy <= y1; yy++)
        faixa(x, x + largura - 1, yy, cor);
}

static int recuo(int k, int raio)
{
    if (raio <= 0 || k >= raio)
        return 0;
    int d = raio - k;
    return raio - (int)raiz((uint32_t)(raio * raio - d * d + raio));
}

static int trecho(int x, int y, int largura, int altura, int raio, int yy, int *a, int *b)
{
    if (largura <= 0 || altura <= 0 || yy < y || yy >= y + altura)
        return 0;
    int maximo = (largura < altura ? largura : altura) / 2;
    if (raio > maximo)
        raio = maximo;
    int k = yy - y;
    if (y + altura - 1 - yy < k)
        k = y + altura - 1 - yy;
    int r = recuo(k, raio);
    *a = x + r;
    *b = x + largura - 1 - r;
    return 1;
}

void retangulo(int x, int y, int largura, int altura, uint16_t cor, int espessura, int raio)
{
    if (!na_banda(y, y + altura - 1))
        return;
    int y0 = y > banda_y0 ? y : banda_y0;
    int y1 = y + altura - 1;
    if (y1 > banda_y0 + BANDA - 1)
        y1 = banda_y0 + BANDA - 1;
    int raio_dentro = raio > espessura ? raio - espessura : 0;
    for (int yy = y0; yy <= y1; yy++) {
        int a, b, c, d;
        if (!trecho(x, y, largura, altura, raio, yy, &a, &b))
            continue;
        if (espessura <= 0 || !trecho(x + espessura, y + espessura, largura - 2 * espessura, altura - 2 * espessura, raio_dentro, yy, &c, &d)) {
            faixa(a, b, yy, cor);
        } else {
            faixa(a, c - 1, yy, cor);
            faixa(d + 1, b, yy, cor);
        }
    }
}

void circulo(int cx, int cy, int raio, uint16_t cor, int espessura)
{
    if (!na_banda(cy - raio, cy + raio))
        return;
    int dentro = espessura > 0 ? raio - espessura : -1;
    int y0 = cy - raio > banda_y0 ? cy - raio : banda_y0;
    int y1 = cy + raio < banda_y0 + BANDA - 1 ? cy + raio : banda_y0 + BANDA - 1;
    for (int y = y0; y <= y1; y++) {
        int dy = y - cy;
        int fora2 = raio * raio + raio - dy * dy;
        if (fora2 < 0)
            continue;
        int h = (int)raiz((uint32_t)fora2);
        int dentro2 = dentro >= 0 ? dentro * dentro + dentro - dy * dy : -1;
        if (dentro < 0 || dentro2 < 0) {
            faixa(cx - h, cx + h, y, cor);
        } else {
            int hd = (int)raiz((uint32_t)dentro2);
            faixa(cx - h, cx - hd - 1, y, cor);
            faixa(cx + hd + 1, cx + h, y, cor);
        }
    }
}

void linha(int x0, int y0, int x1, int y1, uint16_t cor, int espessura)
{
    int topo = (y0 < y1 ? y0 : y1) - espessura;
    int fundo = (y0 > y1 ? y0 : y1) + espessura;
    if (!na_banda(topo, fundo))
        return;
    if (espessura < 1)
        espessura = 1;
    int dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int dy = y1 > y0 ? y1 - y0 : y0 - y1;
    int sx = x0 < x1 ? 1 : -1;
    int sy = y0 < y1 ? 1 : -1;
    int deitada = dx >= dy;
    int erro = dx - dy;
    int x = x0;
    int y = y0;
    for (;;) {
        for (int k = -(espessura / 2); k <= (espessura - 1) / 2; k++) {
            if (deitada)
                ponto(x, y + k, cor);
            else
                ponto(x + k, y, cor);
        }
        if (x == x1 && y == y1)
            break;
        int e2 = 2 * erro;
        if (e2 > -dy) {
            erro -= dy;
            x += sx;
        }
        if (e2 < dx) {
            erro += dx;
            y += sy;
        }
    }
}

void linhas(const int *xy, int pontos, uint16_t cor, int espessura)
{
    for (int i = 0; i + 1 < pontos; i++)
        linha(xy[2 * i], xy[2 * i + 1], xy[2 * i + 2], xy[2 * i + 3], cor, espessura);
}

void poligono(const int *xy, int pontos, uint16_t cor, int espessura)
{
    if (espessura > 0) {
        linhas(xy, pontos, cor, espessura);
        linha(xy[2 * pontos - 2], xy[2 * pontos - 1], xy[0], xy[1], cor, espessura);
        return;
    }
    int topo = xy[1];
    int fundo = xy[1];
    for (int i = 1; i < pontos; i++) {
        if (xy[2 * i + 1] < topo)
            topo = xy[2 * i + 1];
        if (xy[2 * i + 1] > fundo)
            fundo = xy[2 * i + 1];
    }
    if (!na_banda(topo, fundo))
        return;
    if (topo < banda_y0)
        topo = banda_y0;
    if (fundo > banda_y0 + BANDA - 1)
        fundo = banda_y0 + BANDA - 1;
    for (int y = topo; y <= fundo; y++) {
        int menor = 1 << 20;
        int maior = -(1 << 20);
        for (int i = 0; i < pontos; i++) {
            int j = (i + 1) % pontos;
            int xa = xy[2 * i], ya = xy[2 * i + 1];
            int xb = xy[2 * j], yb = xy[2 * j + 1];
            if ((y < ya && y < yb) || (y > ya && y > yb))
                continue;
            int xs[2];
            int n;
            if (ya == yb) {
                xs[0] = xa;
                xs[1] = xb;
                n = 2;
            } else {
                xs[0] = xa + (y - ya) * (xb - xa) / (yb - ya);
                n = 1;
            }
            for (int k = 0; k < n; k++) {
                if (xs[k] < menor)
                    menor = xs[k];
                if (xs[k] > maior)
                    maior = xs[k];
            }
        }
        if (menor <= maior)
            faixa(menor, maior, y, cor);
    }
}

static int trecho_elipse(int x, int y, int largura, int altura, int yy, int *a, int *b)
{
    if (largura <= 0 || altura <= 0 || yy < y || yy >= y + altura)
        return 0;
    int dy = 2 * yy + 1 - (2 * y + altura);
    int resto = altura * altura - dy * dy;
    if (resto < 0)
        return 0;
    int meia = (int)((uint32_t)largura * raiz((uint32_t)resto) / (uint32_t)altura);
    int centro = 2 * x + largura;
    *a = (centro - meia + 1) / 2;
    *b = (centro + meia) / 2 - 1;
    return *a <= *b;
}

void elipse(int x, int y, int largura, int altura, uint16_t cor, int espessura)
{
    if (!na_banda(y, y + altura - 1))
        return;
    int y0 = y > banda_y0 ? y : banda_y0;
    int y1 = y + altura - 1;
    if (y1 > banda_y0 + BANDA - 1)
        y1 = banda_y0 + BANDA - 1;
    for (int yy = y0; yy <= y1; yy++) {
        int a, b, c, d;
        if (!trecho_elipse(x, y, largura, altura, yy, &a, &b))
            continue;
        if (espessura <= 0 || !trecho_elipse(x + espessura, y + espessura, largura - 2 * espessura, altura - 2 * espessura, yy, &c, &d)) {
            faixa(a, b, yy, cor);
        } else {
            faixa(a, c - 1, yy, cor);
            faixa(d + 1, b, yy, cor);
        }
    }
}

int largura_texto(const char *texto, const Fonte *fonte)
{
    int n = 0;
    while (texto[n])
        n++;
    return n * fonte->largura;
}

void texto(const char *texto, uint16_t cor, const Fonte *fonte, int ancora, int x, int y)
{
    int largura = largura_texto(texto, fonte);
    int altura = fonte->altura;
    if (ancora == CENTRO) {
        x -= largura / 2;
        y -= altura / 2;
    } else if (ancora == DIREITA) {
        x -= largura;
    } else if (ancora == MEIO_DIREITA) {
        x -= largura;
        y -= altura / 2;
    }
    if (!na_banda(y, y + altura - 1))
        return;
    int y0 = y > banda_y0 ? y : banda_y0;
    int y1 = y + altura - 1;
    if (y1 > banda_y0 + BANDA - 1)
        y1 = banda_y0 + BANDA - 1;
    for (; *texto; texto++, x += fonte->largura) {
        int c = (unsigned char)*texto;
        if (c < 32 || c > 126)
            c = '?';
        const uint8_t *letra = fonte->dados + (c - 32) * fonte->altura * fonte->bytes_linha;
        for (int yy = y0; yy <= y1; yy++) {
            const uint8_t *linha_letra = letra + (yy - y) * fonte->bytes_linha;
            for (int i = 0; i < fonte->largura; i++) {
                if (linha_letra[i >> 3] & (0x80u >> (i & 7)))
                    ponto(x + i, yy, cor);
            }
        }
    }
}
