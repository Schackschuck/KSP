#include "cena.h"
#include "desenho.h"
#include "navball.h"
#include "texto.h"

#define CENA_X 160
#define CENA_Y 130
#define EXAGERO 3
#define ZOOM_MS 1500u
#define PLANETA_GRANDE 2000
#define COORD_MAX 16000
#define LIMITE_TELA 1000000
#define LONGE 2500
#define PONTOS_VOADO 40
#define PONTOS_FALTA 60
#define PONTOS_ORBITA 96
#define PONTOS_ALVO 120
#define PONTOS_TERRA 40
#define PASSO_COSTA 30
#define FOLGA_CHAO 20
#define MEIO_PESO 128
#define ESCALA_MIN_FOGUETE 83
#define ESCALA_MIN_KSC 11

#define FUNDO RGB(6, 10, 22)
#define TEXTO RGB(240, 240, 240)
#define TRACO RGB(110, 140, 210)
#define VERDE RGB(70, 211, 127)
#define AMBAR RGB(242, 169, 59)
#define ROTULO RGB(130, 150, 200)
#define APAGADO RGB(85, 92, 99)
#define CORPO_NAVE RGB(200, 206, 212)
#define CHAMA RGB(255, 190, 40)
#define CHAMA_MEIO RGB(255, 245, 190)
#define CEU RGB(13, 23, 51)
#define ESTRELA RGB(200, 208, 224)
#define MAR RGB(28, 79, 143)
#define TERRA RGB(46, 111, 60)
#define GELO RGB(219, 230, 239)
#define CINZA_MUN RGB(138, 143, 150)
#define MANCHA_MUN RGB(100, 105, 112)
#define VERDE_MINMUS RGB(140, 205, 178)
#define MANCHA_MINMUS RGB(186, 232, 210)
#define CINZA_CORPO RGB(120, 122, 130)
#define VAB_COR RGB(124, 135, 156)
#define VAB_TETO RGB(92, 102, 124)
#define VAB_PORTA RGB(46, 56, 80)
#define VAB_LISTRA RGB(60, 72, 98)
#define VAB_ANEXO RGB(107, 117, 137)
#define TORRE RGB(110, 124, 150)
#define TANQUE RGB(138, 148, 168)
#define PLATAFORMA RGB(74, 80, 88)

typedef struct {
    int16_t leste, oeste, pontos;
    int16_t dentro[5][2];
} Continente;

typedef struct {
    int32_t s, gy, ref;
} Camera;

typedef struct {
    int32_t x, y, ux, uy, q, sobe;
} Pose;

static const Continente continentes[3] = {
    {885, 1680, 5, {{1680, 700}, {1550, 500}, {1350, 560}, {1150, 420}, {980, 600}}},
    {2050, 2620, 4, {{2620, 660}, {2450, 500}, {2250, 580}, {2080, 700}}},
    {3000, 3350, 3, {{3350, 700}, {3180, 550}, {3030, 720}}},
};
static const int16_t ilhas[3][3] = {{400, 780, 50}, {220, 860, 35}, {2800, 800, 40}};
static const int16_t gelo[12] = {300, 260, 310, 270, 320, 280, 300, 250, 310, 270, 300, 260};
static const int16_t mares_mun[2][6][2] = {
    {{300, 500}, {600, 350}, {900, 500}, {800, 750}, {450, 800}, {250, 650}},
    {{2000, 450}, {2300, 300}, {2600, 450}, {2500, 700}, {2200, 750}, {1950, 620}},
};
static const int16_t crateras_mun[6][3] = {{1200, 800, 90}, {1600, 550, 60}, {200, 250, 70}, {2900, 700, 80}, {3300, 400, 50}, {700, 150, 40}};
static const int16_t planos_minmus[4][3] = {{500, 600, 180}, {1700, 500, 150}, {2700, 650, 170}, {3300, 250, 120}};
static const int16_t estrelas[12][2] = {
    {30, 86}, {70, 140}, {120, 78}, {200, 96}, {250, 76}, {290, 130},
    {310, 90}, {15, 170}, {180, 150}, {95, 110}, {230, 176}, {60, 100},
};

static const int8_t plataforma[8] = {-26, 0, -19, -5, 19, -5, 26, 0};
static const int8_t bracos[6][4] = {
    {-15, -12, -10, -20}, {-10, -12, -15, -20}, {-15, -26, -10, -34},
    {-10, -26, -15, -34}, {-15, -40, -10, -48}, {-10, -40, -15, -48},
};
static const int8_t nariz[6] = {-4, -34, 4, -34, 0, -46};
static const int8_t aleta_esquerda[6] = {-4, -10, -4, 0, -9, 2};
static const int8_t aleta_direita[6] = {4, -10, 4, 0, 9, 2};

static struct {
    int ok;
    DadosCena d;
    int conica;
    int32_t ra, rp, e14, p;
    int nu, nu_chao;
    Camera cam;
    int modo, peso_pad, peso_traj;
    int32_t cy, r_planeta, r_ceu, r_alvo;
    int16_t voado[2 * (PONTOS_VOADO + 1)];
    int16_t falta[2 * (PONTOS_FALTA + 1)];
    int16_t orbita[2 * (PONTOS_ORBITA + 1)];
    int16_t alvo[2 * (PONTOS_ALVO + 1)];
    int n_voado, n_falta, n_orbita, n_alvo;
    int16_t terras[3][2 * PONTOS_TERRA];
    int n_terras[3];
    int16_t gelo[24];
    int32_t cot[3][2];
    int32_t nave_x, nave_y, chao_x, chao_y;
    int32_t cima_x, cima_y, eixo_x, eixo_y;
    int32_t ap_x, ap_y, ap_ux, ap_uy;
    int pe_vis;
    int32_t pe_x, pe_y, pe_ux, pe_uy;
    int alvo_vis;
    int32_t alvo_y;
} cn;

static int modo_atual = -1;
static int modo_antes;
static uint32_t desde;

static int32_t limitar64(int64_t v, int32_t limite)
{
    return v > limite ? limite : v < -limite ? -limite : (int32_t)v;
}

static int32_t dividir64(int64_t n, int32_t d)
{
    if (d == 0)
        return n >= 0 ? INT32_MAX : -INT32_MAX;
    int negativo = (n < 0) != (d < 0);
    uint64_t un = n < 0 ? (uint64_t)(-n) : (uint64_t)n;
    uint32_t ud = d < 0 ? (uint32_t)(-d) : (uint32_t)d;
    uint64_t q = 0;
    uint64_t r = 0;
    for (int i = 0; i < 64; i++) {
        r = (r << 1) | (un >> 63);
        un <<= 1;
        q <<= 1;
        if (r >= ud) {
            r -= ud;
            q |= 1u;
        }
    }
    if (q > INT32_MAX)
        q = INT32_MAX;
    return negativo ? -(int32_t)q : (int32_t)q;
}

static uint32_t raiz64(uint64_t n)
{
    uint64_t r = 0;
    uint64_t bit = (uint64_t)1 << 62;
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
    return (uint32_t)r;
}

static int suave(int t)
{
    return t * t * (768 - 2 * t) >> 16;
}

static uint32_t potencia2(int32_t q16)
{
    if (q16 < 0)
        return 0;
    int n = q16 >> 16;
    uint32_t f = (uint32_t)q16 & 0xFFFFu;
    uint32_t t = 5125;
    t = 14824 + (uint32_t)(((uint64_t)t * f) >> 16);
    t = 45554 + (uint32_t)(((uint64_t)t * f) >> 16);
    uint32_t m = 65536 + (uint32_t)(((uint64_t)t * f) >> 16);
    if (n >= 31)
        return 0x7FFFFFFFu;
    return n >= 16 ? m << (n - 16) : m >> (16 - n);
}

static int32_t raio_conica(int nu)
{
    int32_t den = UM + (int32_t)(((int64_t)cn.e14 * cosseno10(nu)) >> 14);
    if (den < 16)
        return INT32_MAX;
    return dividir64((int64_t)cn.p << 14, den);
}

static int32_t exibido(int32_t r)
{
    int64_t dif = (int64_t)r - cn.d.raio;
    int64_t rd = cn.d.raio;
    for (int i = 0; i < EXAGERO; i++)
        rd += dif;
    return limitar64(rd, 2000000000);
}

static int32_t em_pixels(int32_t metros)
{
    return limitar64(((int64_t)metros * cn.cam.s) >> 24, 2000000000);
}

static void para_tela(int32_t rd, int phi, int32_t *x, int32_t *y)
{
    int32_t wx = (int32_t)(((int64_t)rd * cosseno10(phi)) >> 14);
    int32_t wy = (int32_t)(((int64_t)rd * seno10(phi)) >> 14);
    int32_t dy = wy - cn.d.raio;
    *x = CENA_X + limitar64(((int64_t)wx * cn.cam.s) >> 24, LIMITE_TELA);
    *y = cn.cam.gy - limitar64(((int64_t)dy * cn.cam.s) >> 24, LIMITE_TELA);
}

static void guardar(int16_t *xy, int *n, int32_t x, int32_t y)
{
    xy[2 * *n] = (int16_t)limitar64(x, COORD_MAX);
    xy[2 * *n + 1] = (int16_t)limitar64(y, COORD_MAX);
    (*n)++;
}

static void arco(int16_t *xy, int *n, int de, int ate, int pontos)
{
    *n = 0;
    for (int k = 0; k <= pontos; k++) {
        int nu = de + (ate - de) * k / pontos;
        int32_t rd = exibido(raio_conica(nu));
        if (rd < cn.d.raio / 10 * 6)
            continue;
        int32_t x, y;
        para_tela(rd, 900 + cn.cam.ref - nu, &x, &y);
        guardar(xy, n, x, y);
    }
}

static void unitario(int32_t dx, int32_t dy, int32_t *ux, int32_t *uy)
{
    uint32_t n = raiz64((uint64_t)((int64_t)dx * dx) + (uint64_t)((int64_t)dy * dy));
    if (n == 0) {
        *ux = 0;
        *uy = -UM;
        return;
    }
    *ux = dividir64((int64_t)dx * UM, (int32_t)n);
    *uy = dividir64((int64_t)dy * UM, (int32_t)n);
}

static int32_t cotangente(int phi)
{
    int s = seno10(phi);
    if (s < 64)
        return INT32_MAX;
    return cosseno10(phi) * UM / s;
}

static int longe(int32_t x, int32_t y)
{
    return x < CENA_X - LONGE || x > CENA_X + LONGE || y < CENA_Y - LONGE || y > CENA_Y + LONGE;
}

static Camera camera_do_modo(int modo)
{
    Camera c;
    if (modo == CENA_PAD) {
        int32_t alt = cn.d.alt < 0 ? 0 : cn.d.alt > 1000000 ? 1000000 : cn.d.alt;
        int32_t ext = EXAGERO * alt / 100 * 135 + 140;
        if (ext < 340)
            ext = 340;
        c.s = (96 << 24) / ext;
        c.gy = 174;
        c.ref = cn.nu;
    } else if (modo == CENA_TRAJ) {
        c.s = (84 << 24) / (EXAGERO * cn.d.alvo);
        c.gy = 160;
        c.ref = 1800;
    } else {
        int32_t topo = cn.d.ap_ok && cn.d.ap > cn.d.alvo ? cn.d.ap : cn.d.alvo;
        if (topo > 250000000)
            topo = 250000000;
        int32_t rho = (cn.d.raio + EXAGERO * topo) / 100 * 104;
        c.s = (88 << 24) / (2 * rho);
        if (c.s < 1)
            c.s = 1;
        c.gy = CENA_Y - (int32_t)(((int64_t)cn.d.raio * c.s) >> 24);
        c.ref = cn.nu;
    }
    return c;
}

static Camera misturar(Camera a, Camera b, int t)
{
    Camera c;
    int32_t la = log2q((uint32_t)a.s);
    int32_t lb = log2q((uint32_t)b.s);
    c.s = (int32_t)potencia2(la + (lb - la) * t / 256);
    if (c.s < 1)
        c.s = 1;
    c.gy = a.gy + (b.gy - a.gy) * t / 256;
    c.ref = a.ref + (b.ref - a.ref) * t / 256;
    return c;
}

static void atualizar_modo(int pedido, uint32_t agora)
{
    if (pedido == CENA_MANTER)
        pedido = modo_atual >= 0 ? modo_atual : CENA_PAD;
    if (modo_atual < 0) {
        modo_atual = modo_antes = pedido;
        desde = agora - ZOOM_MS;
    } else if (pedido != modo_atual) {
        modo_antes = modo_atual;
        modo_atual = pedido;
        desde = agora;
    }
}

static void preparar_conica(void)
{
    int32_t ap = cn.d.ap > 900000000 ? 900000000 : cn.d.ap;
    cn.ra = cn.d.raio + ap;
    cn.rp = cn.d.raio + cn.d.pe;
    if (cn.rp < 1)
        cn.rp = 1;
    cn.conica = cn.d.ap_ok && cn.d.pe_ok && cn.rp <= cn.ra;
    if (!cn.conica)
        return;
    cn.e14 = dividir64((int64_t)(cn.ra - cn.rp) * UM, cn.ra + cn.rp);
    cn.p = dividir64((int64_t)cn.ra * cn.rp, (cn.ra + cn.rp) / 2);
    if (cn.rp >= cn.d.raio) {
        cn.nu_chao = 0;
    } else if (cn.ra < cn.d.raio) {
        cn.nu_chao = 1800;
    } else {
        int baixo = 0;
        int alto = 1800;
        while (alto - baixo > 1) {
            int meio = (baixo + alto) / 2;
            if (raio_conica(meio) >= cn.d.raio)
                alto = meio;
            else
                baixo = meio;
        }
        cn.nu_chao = alto;
    }
}

static void preparar_planeta(void)
{
    int32_t x, y;
    for (int i = 0; i < 3; i++) {
        const Continente *k = &continentes[i];
        cn.cot[i][0] = cotangente(k->leste);
        cn.cot[i][1] = cotangente(k->oeste);
        int n = 0;
        if (cn.r_planeta <= PLANETA_GRANDE) {
            for (int phi = k->leste;; phi += PASSO_COSTA) {
                if (phi > k->oeste)
                    phi = k->oeste;
                para_tela(cn.d.raio, phi, &x, &y);
                guardar(cn.terras[i], &n, x, y);
                if (phi == k->oeste)
                    break;
            }
            for (int j = 0; j < k->pontos; j++) {
                para_tela(cn.d.raio / 1000 * k->dentro[j][1], k->dentro[j][0], &x, &y);
                guardar(cn.terras[i], &n, x, y);
            }
        }
        cn.n_terras[i] = n;
    }
    int n = 0;
    for (int i = 0; i < 12; i++) {
        para_tela(cn.d.raio / 1000 * gelo[i], i * 300, &x, &y);
        guardar(cn.gelo, &n, x, y);
    }
}

static void preparar_nave(void)
{
    int phi = 900 + cn.cam.ref - cn.nu;
    int32_t alt = cn.d.alt < 0 ? 0 : cn.d.alt > 900000000 ? 900000000 : cn.d.alt;
    para_tela(exibido(cn.d.raio + alt), phi, &cn.nave_x, &cn.nave_y);
    para_tela(cn.d.raio, phi, &cn.chao_x, &cn.chao_y);
    cn.cima_x = cosseno10(phi);
    cn.cima_y = -seno10(phi);
    int32_t tx = -cn.cima_y;
    int32_t ty = cn.cima_x;
    if (cn.conica) {
        int32_t ax, ay, bx, by;
        para_tela(exibido(raio_conica(cn.nu - 5)), phi + 5, &ax, &ay);
        para_tela(exibido(raio_conica(cn.nu + 5)), phi - 5, &bx, &by);
        if (ax != bx || ay != by)
            unitario(bx - ax, by - ay, &tx, &ty);
    }
    int32_t peso = cn.peso_pad;
    unitario(tx * (256 - peso) + cn.cima_x * peso, ty * (256 - peso) + cn.cima_y * peso, &cn.eixo_x, &cn.eixo_y);
}

static void preparar_marcas(void)
{
    cn.pe_vis = 0;
    if (cn.conica) {
        int phi = 900 + cn.cam.ref - 1800;
        para_tela(exibido(cn.ra), phi, &cn.ap_x, &cn.ap_y);
        cn.ap_ux = cosseno10(phi);
        cn.ap_uy = -seno10(phi);
        if (cn.modo == CENA_ORB && cn.d.pe > 0) {
            phi = 900 + cn.cam.ref;
            para_tela(exibido(cn.rp), phi, &cn.pe_x, &cn.pe_y);
            cn.pe_ux = cosseno10(phi);
            cn.pe_uy = -seno10(phi);
            cn.pe_vis = 1;
        }
    }
    int32_t dx = 296 - CENA_X;
    cn.alvo_vis = cn.peso_traj >= MEIO_PESO && cn.r_alvo > dx;
    if (cn.alvo_vis) {
        uint64_t r2 = (uint64_t)(uint32_t)cn.r_alvo * (uint32_t)cn.r_alvo;
        cn.alvo_y = cn.cy - (int32_t)raiz64(r2 - (uint64_t)(dx * dx));
    }
}

static void preparar(const DadosCena *d, uint32_t agora)
{
    cn.d = *d;
    cn.ok = d->raio > 0;
    if (!cn.ok) {
        modo_atual = -1;
        return;
    }
    if (cn.d.raio < 1000)
        cn.d.raio = 1000;
    if (cn.d.raio > 100000000)
        cn.d.raio = 100000000;
    if (cn.d.alvo < 10000)
        cn.d.alvo = 10000;
    if (cn.d.alvo > 250000000)
        cn.d.alvo = 250000000;
    if (cn.d.topo < 0)
        cn.d.topo = 0;
    if (cn.d.topo > 10000000)
        cn.d.topo = 10000000;
    cn.nu = (d->anom % 3600 + 3600) % 3600;
    preparar_conica();

    atualizar_modo(d->modo, agora);
    uint32_t passou = agora - desde;
    int b = suave(passou >= ZOOM_MS ? 256 : (int)(passou * 256u / ZOOM_MS));
    Camera c1 = camera_do_modo(modo_atual);
    cn.cam = modo_antes != modo_atual && b < 256 ? misturar(camera_do_modo(modo_antes), c1, b) : c1;
    cn.modo = modo_atual;
    cn.peso_pad = modo_atual == CENA_PAD ? 256 : modo_antes == CENA_PAD ? 256 - b : 0;
    if (modo_atual == CENA_TRAJ)
        cn.peso_traj = modo_antes == CENA_TRAJ ? 256 : b;
    else
        cn.peso_traj = modo_antes == CENA_TRAJ ? 256 - b : 0;

    cn.r_planeta = em_pixels(cn.d.raio);
    cn.cy = cn.cam.gy + cn.r_planeta;
    cn.r_ceu = cn.d.topo > 0 ? em_pixels(exibido(cn.d.raio + cn.d.topo)) : 0;
    cn.r_alvo = em_pixels(exibido(cn.d.raio + cn.d.alvo));

    cn.n_voado = cn.n_falta = cn.n_orbita = cn.n_alvo = 0;
    if (cn.peso_pad < MEIO_PESO) {
        if (cn.conica && cn.modo == CENA_ORB) {
            arco(cn.orbita, &cn.n_orbita, 0, 3600, PONTOS_ORBITA);
        } else if (cn.conica) {
            int de = cn.nu_chao > 0 ? cn.nu_chao - FOLGA_CHAO : 0;
            int ate = cn.nu_chao > 0 ? 3600 - cn.nu_chao + FOLGA_CHAO : 3600;
            int nu = cn.nu < de ? de : cn.nu > ate ? ate : cn.nu;
            arco(cn.voado, &cn.n_voado, de, nu, PONTOS_VOADO);
            arco(cn.falta, &cn.n_falta, nu, ate, PONTOS_FALTA);
        }
        int32_t rd = exibido(cn.d.raio + cn.d.alvo);
        for (int k = 0; k <= PONTOS_ALVO; k++) {
            int32_t x, y;
            para_tela(rd, k * 3600 / PONTOS_ALVO, &x, &y);
            guardar(cn.alvo, &cn.n_alvo, x, y);
        }
    }
    preparar_planeta();
    preparar_nave();
    preparar_marcas();
}

static int codigo(int x, int y)
{
    int c = 0;
    if (x < 0)
        c |= 1;
    else if (x >= LARGURA)
        c |= 2;
    if (y < CENA_TOPO)
        c |= 4;
    else if (y > CENA_FUNDO)
        c |= 8;
    return c;
}

static void segmento(int x0, int y0, int x1, int y1, uint16_t cor, int espessura)
{
    int topo = y0 < y1 ? y0 : y1;
    int fundo = y0 > y1 ? y0 : y1;
    if (!na_banda(topo - espessura, fundo + espessura))
        return;
    int c0 = codigo(x0, y0);
    int c1 = codigo(x1, y1);
    while (c0 | c1) {
        if (c0 & c1)
            return;
        int c = c0 ? c0 : c1;
        int x, y;
        if (c & 8) {
            y = CENA_FUNDO;
            x = x0 + (x1 - x0) * (y - y0) / (y1 - y0);
        } else if (c & 4) {
            y = CENA_TOPO;
            x = x0 + (x1 - x0) * (y - y0) / (y1 - y0);
        } else if (c & 2) {
            x = LARGURA - 1;
            y = y0 + (y1 - y0) * (x - x0) / (x1 - x0);
        } else {
            x = 0;
            y = y0 + (y1 - y0) * (x - x0) / (x1 - x0);
        }
        if (c == c0) {
            x0 = x;
            y0 = y;
            c0 = codigo(x0, y0);
        } else {
            x1 = x;
            y1 = y;
            c1 = codigo(x1, y1);
        }
    }
    linha(x0, y0, x1, y1, cor, espessura);
}

static void tracar(const int16_t *xy, int n, uint16_t cor, int espessura, int tracejado)
{
    for (int i = 0; i + 1 < n; i++) {
        if (!tracejado || !(i & 1))
            segmento(xy[2 * i], xy[2 * i + 1], xy[2 * i + 2], xy[2 * i + 3], cor, espessura);
    }
}

static void area(const int16_t *xy, int n, uint16_t cor)
{
    if (n < 3)
        return;
    int topo = xy[1];
    int fundo = xy[1];
    for (int i = 1; i < n; i++) {
        if (xy[2 * i + 1] < topo)
            topo = xy[2 * i + 1];
        if (xy[2 * i + 1] > fundo)
            fundo = xy[2 * i + 1];
    }
    if (topo < banda_y0)
        topo = banda_y0;
    if (topo < CENA_TOPO)
        topo = CENA_TOPO;
    if (fundo > banda_y0 + BANDA - 1)
        fundo = banda_y0 + BANDA - 1;
    if (fundo > CENA_FUNDO)
        fundo = CENA_FUNDO;
    for (int y = topo; y <= fundo; y++) {
        int xs[16];
        int k = 0;
        for (int i = 0; i < n; i++) {
            int j = i + 1 == n ? 0 : i + 1;
            int ya = xy[2 * i + 1];
            int yb = xy[2 * j + 1];
            if ((ya <= y) == (yb <= y))
                continue;
            int xa = xy[2 * i];
            int xb = xy[2 * j];
            if (k < 16)
                xs[k++] = xa + (y - ya) * (xb - xa) / (yb - ya);
        }
        for (int a = 1; a < k; a++) {
            int v = xs[a];
            int b = a - 1;
            while (b >= 0 && xs[b] > v) {
                xs[b + 1] = xs[b];
                b--;
            }
            xs[b + 1] = v;
        }
        for (int m = 0; m + 1 < k; m += 2)
            faixa(xs[m], xs[m + 1], y, cor);
    }
}

static int linhas_da_cena(int *y0, int *y1)
{
    *y0 = banda_y0 > CENA_TOPO ? banda_y0 : CENA_TOPO;
    *y1 = banda_y0 + BANDA - 1 < CENA_FUNDO ? banda_y0 + BANDA - 1 : CENA_FUNDO;
    return *y0 <= *y1;
}

static int32_t meia_corda(int32_t r, int32_t d)
{
    if (d < 0)
        d = -d;
    if (d > r)
        return -1;
    return (int32_t)raiz64((uint64_t)(uint32_t)(r - d) * (uint32_t)(r + d));
}

static void disco(int32_t cy, int32_t r, uint16_t cor)
{
    int y0, y1;
    if (!linhas_da_cena(&y0, &y1))
        return;
    for (int y = y0; y <= y1; y++) {
        int32_t w = meia_corda(r, y - cy);
        if (w >= 0)
            faixa(limitar64((int64_t)CENA_X - w, LIMITE_TELA), limitar64((int64_t)CENA_X + w, LIMITE_TELA), y, cor);
    }
}

static int32_t borda(int32_t cot, int32_t dy, int32_t infinito)
{
    if (cot == INT32_MAX)
        return infinito;
    return CENA_X - limitar64(((int64_t)dy * cot) >> 14, LIMITE_TELA);
}

static void planeta_grande(uint16_t base)
{
    int y0, y1;
    if (!linhas_da_cena(&y0, &y1))
        return;
    for (int y = y0; y <= y1; y++) {
        int32_t dy = y - cn.cy;
        int32_t w = meia_corda(cn.r_planeta, dy);
        if (w < 0)
            continue;
        int32_t xa = limitar64((int64_t)CENA_X - w, LIMITE_TELA);
        int32_t xb = limitar64((int64_t)CENA_X + w, LIMITE_TELA);
        faixa(xa, xb, y, base);
        if (cn.d.corpo != CORPO_KERBIN || dy >= 0)
            continue;
        for (int i = 0; i < 3; i++) {
            if (cn.cot[i][0] == INT32_MAX && cn.cot[i][1] == INT32_MAX)
                continue;
            int32_t leste = borda(cn.cot[i][0], dy, LIMITE_TELA);
            int32_t oeste = borda(cn.cot[i][1], dy, -LIMITE_TELA);
            int32_t a = oeste > xa ? oeste : xa;
            int32_t b = leste < xb ? leste : xb;
            if (a <= b)
                faixa(a, b, y, TERRA);
        }
    }
}

static void mancha(int phi, int fracao, int raio_mil, uint16_t cor, int espessura)
{
    int32_t x, y;
    para_tela(cn.d.raio / 1000 * fracao, phi, &x, &y);
    int r = (int)(cn.r_planeta * raio_mil / 1000);
    if (r >= 1 && !longe(x, y))
        circulo((int)x, (int)y, r, cor, espessura);
}

static void planeta_pequeno(uint16_t base)
{
    disco(cn.cy, cn.r_planeta, base);
    if (cn.d.corpo == CORPO_KERBIN) {
        for (int i = 0; i < 3; i++)
            area(cn.terras[i], cn.n_terras[i], TERRA);
        for (int i = 0; i < 3; i++)
            mancha(ilhas[i][0], ilhas[i][1], ilhas[i][2], TERRA, 0);
        area(cn.gelo, 12, GELO);
    } else if (cn.d.corpo == CORPO_MUN) {
        for (int i = 0; i < 2; i++) {
            int16_t xy[12];
            int n = 0;
            for (int j = 0; j < 6; j++) {
                int32_t x, y;
                para_tela(cn.d.raio / 1000 * mares_mun[i][j][1], mares_mun[i][j][0], &x, &y);
                guardar(xy, &n, x, y);
            }
            area(xy, n, MANCHA_MUN);
        }
        for (int i = 0; i < 6; i++)
            mancha(crateras_mun[i][0], crateras_mun[i][1], crateras_mun[i][2], MANCHA_MUN, 1);
    } else if (cn.d.corpo == CORPO_MINMUS) {
        for (int i = 0; i < 4; i++)
            mancha(planos_minmus[i][0], planos_minmus[i][1], planos_minmus[i][2], MANCHA_MINMUS, 0);
    }
}

static void pose_ponto(const Pose *p, int lx, int ly, int *x, int *y)
{
    ly -= p->sobe;
    int32_t rx = -p->uy;
    int32_t ry = p->ux;
    *x = (int)(p->x + (((int64_t)(lx * rx - ly * p->ux) * p->q) >> 22));
    *y = (int)(p->y + (((int64_t)(lx * ry - ly * p->uy) * p->q) >> 22));
}

static void pose_poligono(const Pose *p, const int8_t *pontos, int n, uint16_t cor)
{
    int xy[8];
    for (int i = 0; i < n; i++)
        pose_ponto(p, pontos[2 * i], pontos[2 * i + 1], &xy[2 * i], &xy[2 * i + 1]);
    poligono(xy, n, cor, 0);
}

static void pose_retangulo(const Pose *p, int x0, int y0, int x1, int y1, uint16_t cor)
{
    int8_t cantos[8] = {(int8_t)x0, (int8_t)y0, (int8_t)x1, (int8_t)y0, (int8_t)x1, (int8_t)y1, (int8_t)x0, (int8_t)y1};
    pose_poligono(p, cantos, 4, cor);
}

static void pose_linha(const Pose *p, int x0, int y0, int x1, int y1, uint16_t cor, int espessura)
{
    int ax, ay, bx, by;
    pose_ponto(p, x0, y0, &ax, &ay);
    pose_ponto(p, x1, y1, &bx, &by);
    int e = espessura * p->q >> 8;
    segmento(ax, ay, bx, by, cor, e < 1 ? 1 : e);
}

static void desenhar_ksc(void)
{
    int32_t q = (int32_t)(((int64_t)cn.cam.s * 3) >> 16);
    if (cn.d.corpo != CORPO_KERBIN || cn.peso_pad < MEIO_PESO || q < ESCALA_MIN_KSC || longe(cn.chao_x, cn.chao_y))
        return;
    Pose p = {cn.chao_x, cn.chao_y, cn.cima_x, cn.cima_y, q, 0};
    pose_poligono(&p, plataforma, 4, PLATAFORMA);
    pose_linha(&p, -15, -5, -15, -58, TORRE, 2);
    pose_linha(&p, -10, -5, -10, -58, TORRE, 2);
    for (int i = 0; i < 6; i++)
        pose_linha(&p, bracos[i][0], bracos[i][1], bracos[i][2], bracos[i][3], TORRE, 1);
    pose_linha(&p, -10, -42, -4, -42, TORRE, 2);
    pose_linha(&p, 26, 0, 28, -26, TORRE, 1);
    pose_linha(&p, 34, 0, 32, -26, TORRE, 1);
    int tx, ty;
    pose_ponto(&p, 30, -31, &tx, &ty);
    int rt = 6 * q >> 8;
    circulo(tx, ty, rt < 1 ? 1 : rt, TANQUE, 0);
    pose_retangulo(&p, -112, -70, -56, 0, VAB_COR);
    pose_retangulo(&p, -114, -74, -54, -69, VAB_TETO);
    pose_retangulo(&p, -97, -62, -73, 0, VAB_PORTA);
    for (int y = -48; y <= -20; y += 14)
        pose_linha(&p, -97, y, -73, y, VAB_LISTRA, 1);
    pose_retangulo(&p, -56, -30, -38, 0, VAB_ANEXO);
    pose_linha(&p, -64, -74, -64, -86, VAB_TETO, 1);
}

static void desenhar_foguete(void)
{
    if (longe(cn.nave_x, cn.nave_y))
        return;
    int32_t q = (int32_t)(((int64_t)cn.cam.s * 3) >> 16);
    if (q < ESCALA_MIN_FOGUETE)
        q = ESCALA_MIN_FOGUETE;
    if (q > 512)
        q = 512;
    Pose p = {cn.nave_x, cn.nave_y, cn.eixo_x, cn.eixo_y, q, 5 * cn.peso_pad / 256};
    if (cn.d.motor > 0) {
        int l = 6 + 16 * (cn.d.motor > 100 ? 100 : cn.d.motor) / 100;
        int8_t chama[6] = {-3, 2, 3, 2, 0, (int8_t)(2 + l)};
        pose_poligono(&p, chama, 3, CHAMA);
        int8_t meio[6] = {-1, 2, 1, 2, 0, (int8_t)(2 + l * 55 / 100)};
        pose_poligono(&p, meio, 3, CHAMA_MEIO);
    }
    pose_retangulo(&p, -2, 0, 2, 2, APAGADO);
    pose_retangulo(&p, -4, -34, 4, 0, CORPO_NAVE);
    pose_linha(&p, -4, -22, 4, -22, APAGADO, 1);
    pose_poligono(&p, nariz, 3, CORPO_NAVE);
    pose_poligono(&p, aleta_esquerda, 3, APAGADO);
    pose_poligono(&p, aleta_direita, 3, APAGADO);
}

static void rotulo(const char *t, int32_t x, int32_t y, int32_t ux)
{
    int topo = (int)y - fonte_pequena.altura / 2;
    if (topo < CENA_TOPO)
        topo = CENA_TOPO;
    if (topo > CENA_FUNDO - fonte_pequena.altura)
        topo = CENA_FUNDO - fonte_pequena.altura;
    if (ux >= 0)
        texto(t, TEXTO, &fonte_pequena, CANTO, (int)x + 8, topo);
    else
        texto(t, TEXTO, &fonte_pequena, DIREITA, (int)x - 8, topo);
}

static void marca(int32_t x, int32_t y, int32_t ux, int32_t uy, uint16_t cor)
{
    segmento((int)(x - (ux * 4 >> 14)), (int)(y - (uy * 4 >> 14)), (int)(x + (ux * 4 >> 14)), (int)(y + (uy * 4 >> 14)), cor, 2);
}

static void desenhar_marcas(void)
{
    char buf[24];
    if (cn.peso_pad >= MEIO_PESO)
        return;
    if (cn.conica && !longe(cn.ap_x, cn.ap_y)) {
        marca(cn.ap_x, cn.ap_y, cn.ap_ux, cn.ap_uy, AMBAR);
        formatar_distancia(escrever_texto(buf, "AP "), 1, cn.d.ap);
        if (cn.modo == CENA_ORB) {
            rotulo(buf, cn.ap_x, cn.ap_y, cn.ap_ux);
        } else {
            int y = (int)cn.ap_y - 12;
            if (y - fonte_pequena.altura / 2 < CENA_TOPO)
                y = (int)cn.ap_y + 13;
            texto(buf, TEXTO, &fonte_pequena, CENTRO, (int)cn.ap_x, y);
        }
    }
    if (cn.pe_vis && !longe(cn.pe_x, cn.pe_y)) {
        marca(cn.pe_x, cn.pe_y, cn.pe_ux, cn.pe_uy, ROTULO);
        formatar_distancia(escrever_texto(buf, "PE "), 1, cn.d.pe);
        rotulo(buf, cn.pe_x, cn.pe_y, cn.pe_ux);
    }
    if (cn.alvo_vis) {
        formatar_distancia(escrever_texto(buf, "ALVO "), 1, cn.d.alvo);
        texto(buf, AMBAR, &fonte_pequena, DIREITA, 304, (int)cn.alvo_y - 4 - fonte_pequena.altura);
    }
}

static uint16_t cor_do_corpo(void)
{
    if (cn.d.corpo == CORPO_KERBIN)
        return MAR;
    if (cn.d.corpo == CORPO_MUN)
        return CINZA_MUN;
    if (cn.d.corpo == CORPO_MINMUS)
        return VERDE_MINMUS;
    return CINZA_CORPO;
}

void cena_esquecer(void)
{
    modo_atual = -1;
}

void cena_desenhar(const DadosCena *d, uint32_t agora)
{
    if (banda_y0 == 0)
        preparar(d, agora);
    if (!cn.ok || !na_banda(CENA_TOPO, CENA_FUNDO))
        return;
    for (int i = 0; i < 12; i++)
        ponto(estrelas[i][0], estrelas[i][1], ESTRELA);
    if (cn.r_ceu > 0)
        disco(cn.cy, cn.r_ceu, CEU);
    tracar(cn.alvo, cn.n_alvo, AMBAR, 1, 1);
    if (cn.modo == CENA_ORB) {
        tracar(cn.orbita, cn.n_orbita, VERDE, 2, 0);
    } else {
        tracar(cn.falta, cn.n_falta, TRACO, 1, 1);
        tracar(cn.voado, cn.n_voado, VERDE, 2, 0);
    }
    if (cn.r_planeta > PLANETA_GRANDE)
        planeta_grande(cor_do_corpo());
    else
        planeta_pequeno(cor_do_corpo());
    desenhar_ksc();
    desenhar_marcas();
    desenhar_foguete();
    preencher(0, 0, LARGURA, CENA_TOPO, FUNDO);
    preencher(0, CENA_FUNDO + 1, LARGURA, ALTURA - CENA_FUNDO - 1, FUNDO);
}
