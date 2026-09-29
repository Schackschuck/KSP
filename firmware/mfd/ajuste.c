#include <stdint.h>

#include "ajuste.h"
#include "desenho.h"
#include "lcd.h"
#include "lpc2148.h"
#include "relogio.h"
#include "texto.h"
#include "toque.h"

#define MARCA 0x4B535031u
#define SETOR 26u
#define ENDERECO 0x7C000u
#define OPCOES 8
#define SEGURAR_MS 2000u
#define ESPERA_PRIMEIRA_MS 30000u
#define TESTE_MS 10000u

typedef struct {
    uint32_t marca;
    uint32_t orientacao;
    uint32_t trocar;
    int32_t u0, u1, v0, v2;
    uint32_t soma;
} Ajuste;

typedef void (*Iap)(uint32_t *, uint32_t *);

static const uint8_t orientacoes[OPCOES] = {0x68, 0xA8, 0x28, 0xE8, 0x60, 0xA0, 0x20, 0xE0};
static const int pontos[3][2] = {{30, 30}, {290, 30}, {30, 210}};

static Ajuste atual = {MARCA, 0, 0, 100, 900, 100, 900, 0};
static uint32_t bloco[64];
static uint32_t comando[5];
static uint32_t resultado[5];

enum { ORIENTACAO, PONTO, TESTE, MENSAGEM };

static int etapa;
static int ponto_atual;
static int toque_x = -1, toque_y = -1;
static const char *mensagem;
static uint16_t cor_mensagem;

#define FUNDO RGB(6, 10, 22)
#define TEXTO RGB(240, 240, 240)
#define ROTULO RGB(130, 150, 200)
#define VERDE RGB(70, 211, 127)
#define AMBAR RGB(242, 169, 59)

static uint32_t soma(const Ajuste *a)
{
    const uint32_t *p = (const uint32_t *)a;
    uint32_t total = 0xA5A5A5A5u;
    for (unsigned i = 0; i < sizeof(Ajuste) / 4 - 1; i++)
        total += p[i] ^ (i * 0x9E3779B9u);
    return total;
}

static int valido(const Ajuste *a)
{
    return a->marca == MARCA && a->soma == soma(a) && a->orientacao < OPCOES && a->u1 != a->u0 && a->v2 != a->v0;
}

int ajuste_carregar(void)
{
    const Ajuste *salvo = (const Ajuste *)ENDERECO;
    int ok = valido(salvo);
    if (ok)
        atual = *salvo;
    lcd_orientacao(orientacoes[atual.orientacao]);
    return ok;
}

int ajuste_mapear(int u, int v, int *x, int *y)
{
    if (atual.trocar) {
        int t = u;
        u = v;
        v = t;
    }
    *x = pontos[0][0] + (u - atual.u0) * (pontos[1][0] - pontos[0][0]) / (atual.u1 - atual.u0);
    *y = pontos[0][1] + (v - atual.v0) * (pontos[2][1] - pontos[0][1]) / (atual.v2 - atual.v0);
    return *x >= 0 && *x < LARGURA && *y >= 0 && *y < ALTURA;
}

static uint32_t desligar_interrupcoes(void)
{
    uint32_t cpsr;
    __asm__ volatile("mrs %0, cpsr" : "=r"(cpsr));
    __asm__ volatile("msr cpsr_c, %0" : : "r"(cpsr | 0xC0u) : "memory");
    return cpsr;
}

static void religar_interrupcoes(uint32_t cpsr)
{
    __asm__ volatile("msr cpsr_c, %0" : : "r"(cpsr) : "memory");
}

static int iap(uint32_t codigo, uint32_t a, uint32_t b, uint32_t c, uint32_t d)
{
    comando[0] = codigo;
    comando[1] = a;
    comando[2] = b;
    comando[3] = c;
    comando[4] = d;
    ((Iap)0x7FFFFFF1u)(comando, resultado);
    return resultado[0] == 0;
}

static int salvar(void)
{
    atual.marca = MARCA;
    atual.soma = soma(&atual);
    for (unsigned i = 0; i < 64; i++)
        bloco[i] = 0xFFFFFFFFu;
    const uint32_t *p = (const uint32_t *)&atual;
    for (unsigned i = 0; i < sizeof(Ajuste) / 4; i++)
        bloco[i] = p[i];
    uint32_t cpsr = desligar_interrupcoes();
    int ok = iap(50, SETOR, SETOR, 0, 0) && iap(52, SETOR, SETOR, CCLK_KHZ, 0) && iap(50, SETOR, SETOR, 0, 0) &&
             iap(51, ENDERECO, (uint32_t)bloco, 256, CCLK_KHZ);
    religar_interrupcoes(cpsr);
    return ok && valido((const Ajuste *)ENDERECO);
}

static void cruz(int x, int y, uint16_t cor)
{
    linha(x - 12, y, x + 12, y, cor, 1);
    linha(x, y - 12, x, y + 12, cor, 1);
    circulo(x, y, 5, cor, 1);
}

static void cena(void)
{
    preencher(0, 0, LARGURA, ALTURA, FUNDO);
    char buf[32];
    if (etapa == ORIENTACAO) {
        preencher(0, 0, 60, 40, RGB(255, 0, 0));
        texto("1", RGB(255, 255, 255), &fonte_grande, CENTRO, 30, 20);
        preencher(260, 0, 60, 40, RGB(0, 255, 0));
        texto("2", RGB(0, 0, 0), &fonte_grande, CENTRO, 290, 20);
        preencher(0, 200, 60, 40, RGB(0, 0, 255));
        texto("3", RGB(255, 255, 255), &fonte_grande, CENTRO, 30, 220);
        texto("AJUSTE DA TELA", TEXTO, &fonte_media, CENTRO, 160, 24);
        char *p = escrever_texto(buf, "OPCAO ");
        p = escrever_inteiro(p, (int32_t)atual.orientacao + 1, 1);
        escrever_texto(p, " DE 8");
        texto(buf, AMBAR, &fonte_normal, CENTRO, 160, 62);
        texto("CERTO: 1 VERMELHO EM CIMA A", ROTULO, &fonte_pequena, CENTRO, 160, 92);
        texto("ESQUERDA, 2 VERDE, 3 AZUL, E O", ROTULO, &fonte_pequena, CENTRO, 160, 106);
        texto("TEXTO SE LE NORMALMENTE", ROTULO, &fonte_pequena, CENTRO, 160, 120);
        texto("TOQUE: PROXIMA OPCAO", TEXTO, &fonte_normal, CENTRO, 160, 150);
        texto("SEGURE 2 S: ESTA CERTA", TEXTO, &fonte_normal, CENTRO, 160, 172);
        p = escrever_texto(buf, "CONTROLADOR ");
        escrever_hex(p, lcd_id(), 4);
        texto(buf, ROTULO, &fonte_pequena, DIREITA, 314, 222);
    } else if (etapa == PONTO) {
        cruz(pontos[ponto_atual][0], pontos[ponto_atual][1], TEXTO);
        texto("TOQUE NO CENTRO DA CRUZ", TEXTO, &fonte_normal, CENTRO, 160, 110);
        char *p = escrever_texto(buf, "PONTO ");
        p = escrever_inteiro(p, ponto_atual + 1, 1);
        escrever_texto(p, " DE 3");
        texto(buf, ROTULO, &fonte_pequena, CENTRO, 160, 134);
    } else if (etapa == TESTE) {
        texto("AJUSTE SALVO", VERDE, &fonte_media, CENTRO, 160, 90);
        texto("TOQUE PARA CONFERIR", TEXTO, &fonte_normal, CENTRO, 160, 120);
        texto("SAI SOZINHO EM 10 S SEM TOQUE", ROTULO, &fonte_pequena, CENTRO, 160, 144);
        if (toque_x >= 0)
            cruz(toque_x, toque_y, AMBAR);
    } else {
        texto(mensagem, cor_mensagem, &fonte_normal, CENTRO, 160, 120);
    }
}

static void mostrar(void)
{
    desenhar_quadro(cena);
}

static void avisar(const char *texto_aviso, uint16_t cor, uint32_t ms)
{
    etapa = MENSAGEM;
    mensagem = texto_aviso;
    cor_mensagem = cor;
    mostrar();
    esperar_ms(ms);
}

static void esperar_soltar(void)
{
    int soltos = 0;
    int u, v;
    while (soltos < 5) {
        soltos = toque_ler(&u, &v) ? 0 : soltos + 1;
        esperar_ms(20);
    }
}

static int esperar_toque(uint32_t limite_ms)
{
    uint32_t inicio = relogio_ms();
    int u, v;
    while (!toque_ler(&u, &v)) {
        if (limite_ms && relogio_ms() - inicio >= limite_ms)
            return 0;
        esperar_ms(20);
    }
    return 1;
}

static int segurou(void)
{
    uint32_t inicio = relogio_ms();
    int soltos = 0;
    int u, v;
    while (soltos < 3) {
        if (relogio_ms() - inicio >= SEGURAR_MS)
            return 1;
        soltos = toque_ler(&u, &v) ? 0 : soltos + 1;
        esperar_ms(20);
    }
    return 0;
}

static int escolher_orientacao(int primeira_vez)
{
    etapa = ORIENTACAO;
    for (;;) {
        mostrar();
        if (!esperar_toque(primeira_vez ? ESPERA_PRIMEIRA_MS : 0))
            return 0;
        primeira_vez = 0;
        if (segurou()) {
            avisar("ORIENTACAO ESCOLHIDA", VERDE, 800);
            esperar_soltar();
            return 1;
        }
        atual.orientacao = (atual.orientacao + 1) % OPCOES;
        lcd_orientacao(orientacoes[atual.orientacao]);
    }
}

static void ler_ponto(int *u, int *v)
{
    for (;;) {
        esperar_toque(0);
        int32_t su = 0, sv = 0;
        int n = 0;
        int a, b;
        while (n < 16 && toque_ler(&a, &b)) {
            su += a;
            sv += b;
            n++;
            esperar_ms(15);
        }
        esperar_soltar();
        if (n >= 4) {
            *u = su / n;
            *v = sv / n;
            return;
        }
    }
}

static int calibrar(void)
{
    int u[3], v[3];
    etapa = PONTO;
    for (ponto_atual = 0; ponto_atual < 3; ponto_atual++) {
        mostrar();
        ler_ponto(&u[ponto_atual], &v[ponto_atual]);
    }
    int du = u[1] - u[0];
    int dv = v[1] - v[0];
    int trocar = (du < 0 ? -du : du) < (dv < 0 ? -dv : dv);
    if (trocar) {
        for (int i = 0; i < 3; i++) {
            int t = u[i];
            u[i] = v[i];
            v[i] = t;
        }
    }
    int largura_u = u[1] - u[0];
    int altura_v = v[2] - v[0];
    if ((largura_u < 0 ? -largura_u : largura_u) < 100 || (altura_v < 0 ? -altura_v : altura_v) < 80)
        return 0;
    atual.trocar = (uint32_t)trocar;
    atual.u0 = u[0];
    atual.u1 = u[1];
    atual.v0 = v[0];
    atual.v2 = v[2];
    return 1;
}

static void conferir(void)
{
    etapa = TESTE;
    toque_x = -1;
    mostrar();
    uint32_t ultimo = relogio_ms();
    while (relogio_ms() - ultimo < TESTE_MS) {
        int u, v, x, y;
        if (toque_ler(&u, &v)) {
            ultimo = relogio_ms();
            ajuste_mapear(u, v, &x, &y);
            if (x != toque_x || y != toque_y) {
                toque_x = x;
                toque_y = y;
                mostrar();
            }
        }
        esperar_ms(30);
    }
}

int ajuste_pedido(void)
{
    int u, v;
    for (int i = 0; i < 3; i++) {
        if (!toque_ler(&u, &v))
            return 0;
        esperar_ms(100);
    }
    return 1;
}

void ajuste_executar(int primeira_vez)
{
    if (!escolher_orientacao(primeira_vez))
        return;
    while (!calibrar())
        avisar("NAO DEU CERTO, DE NOVO", AMBAR, 1500);
    if (!salvar()) {
        avisar("ERRO AO SALVAR NA FLASH", AMBAR, 3000);
        return;
    }
    conferir();
}
