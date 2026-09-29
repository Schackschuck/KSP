#include "mfd.h"
#include "desenho.h"
#include "navball.h"
#include "serial.h"
#include "texto.h"

#define MAX_LINHA 31
#define MAX_PARTES 6
#define SEM_SINAL_MS 1000u
#define DESTAQUE_MS 200u

#define BOLA_X 160
#define BOLA_Y 98
#define ARO_RAIO 76
#define RAIO_BOTAO 13
#define VISIVEL_MIN 4915

#define RODA_X 160
#define RODA_Y 104
#define RODA_RAIO 78
#define RODA_MODOS 52
#define RODA_BOTAO 14

#define POUSO_CHAO 200
#define POUSO_TOPO 58

#define FUNDO RGB(6, 10, 22)
#define TEXTO RGB(240, 240, 240)
#define ROTULO RGB(130, 150, 200)
#define ARO RGB(22, 32, 60)
#define BORDA RGB(60, 80, 140)
#define TRACO RGB(110, 140, 210)
#define COR_VEL RGB(235, 190, 40)
#define COR_ALT RGB(225, 70, 200)
#define COR_ACEL RGB(90, 120, 255)
#define VV_SOBE RGB(60, 200, 90)
#define VV_DESCE RGB(240, 200, 40)
#define VV_DESCE_RAPIDO RGB(240, 60, 40)
#define BOTAO_APAGADO RGB(40, 50, 80)
#define BOTAO_LIGADO RGB(40, 170, 80)
#define BORDA_LIGADO RGB(130, 240, 150)
#define NAVE RGB(255, 140, 0)
#define AVISO RGB(230, 60, 40)
#define NUMERO_RUMO RGB(255, 255, 255)
#define NUMERO_PITCH RGB(200, 215, 240)
#define SOMBRA_NUMERO RGB(10, 15, 30)
#define COR_PRO RGB(230, 210, 40)
#define COR_NRM RGB(200, 70, 255)
#define COR_RDL RGB(60, 210, 230)
#define COR_TGT RGB(255, 140, 200)
#define COR_MNV RGB(60, 130, 255)
#define COR_FBW RGB(90, 230, 90)
#define AZUL RGB(76, 157, 255)
#define VERDE RGB(70, 211, 127)
#define AMBAR RGB(242, 169, 59)
#define APAGADO RGB(85, 92, 99)
#define FUNDO_MODO RGB(17, 23, 29)
#define CHAO_POUSO RGB(16, 24, 40)
#define ALVO_POUSO RGB(220, 40, 70)
#define TRACEJADO RGB(40, 150, 220)
#define CORPO_NAVE RGB(200, 206, 212)
#define CHAMA RGB(255, 190, 40)
#define CHAMA_MEIO RGB(255, 245, 190)

enum { M_PRO, M_NRM, M_RDL, M_TGT, M_MNV, M_FBW, MARCADORES };
enum { N_VEL, N_AP, N_PE, N_TAP, N_TPE, N_DIST, N_VV, N_ACEL, NUMEROS };
enum { P_ALT, P_VV, P_MOTOR, P_TWR, P_FREADA, P_IGN, P_INCL, CAMPOS_POUSO };
enum { PAG_NAV, PAG_SAS, PAG_AP, PAG_POUSO };
enum { MODO_NENHUM, MODO_SUP, MODO_ORB, MODO_ALVO };
enum { SCR_OFF, SCR_ATIVO, SCR_FIM, SCR_ABORT, SCR_FALHA, SCR_LIGA, SCR_DESL };
enum { SAS_ESTAB, SAS_MAN, SAS_PRO, SAS_RETRO, SAS_NRM, SAS_ANRM, SAS_RFORA, SAS_RDENTRO, SAS_ALVO, SAS_AALVO, MODOS_SAS };
enum { BOTAO_MODO, BOTAO_RCS, BOTAO_SAS, BOTAO_NENHUM };

typedef struct {
    int valido;
    int32_t valor;
} Numero;

static const char *const nomes_marcadores[MARCADORES] = {"PRO", "NRM", "RDL", "TGT", "MNV", "FBW"};
static const char *const nomes_numeros[NUMEROS] = {"VEL", "AP", "PE", "TAP", "TPE", "DIST", "VV", "ACEL"};
static const char *const nomes_pouso[CAMPOS_POUSO] = {"ALT", "VV", "MOTOR", "TWR", "FREADA", "IGN", "INCL"};
static const char *const nomes_paginas[] = {"NAV", "SAS", "AP", "POUSO"};
static const char *const nomes_modos[] = {"", "SUP", "ORB", "ALVO"};
static const char *const nomes_scr[] = {"OFF", "ATIVO", "FIM", "ABORT", "FALHA", "LIGA", "DESL"};
static const char *const nomes_sas[MODOS_SAS] = {"ESTAB", "MAN", "PRO", "RETRO", "NRM", "ANRM", "RFORA", "RDENTRO", "ALVO", "AALVO"};
static const char *const nomes_ap[3] = {"HDG", "ALT", "VS"};
static const char *const rotulos_ap[3] = {"HDG", "ALT", "V/S"};
static const char *const nomes_leis[4] = {"FBW", "DIRETA", "CHAO", "OFF"};
static const char *const textos_leis[4] = {"LEI FBW", "LEI DIRETA", "NO CHAO", "FBW FECHADO"};
static const uint16_t cores_leis[4] = {VERDE, AMBAR, APAGADO, APAGADO};

static const int modos_roda[6] = {SAS_NRM, SAS_PRO, SAS_RFORA, SAS_ANRM, SAS_RETRO, SAS_RDENTRO};
static const int angulos_roda[6] = {-90, -30, 30, 90, 150, -150};
static const int modos_faixa[4] = {SAS_ESTAB, SAS_MAN, SAS_ALVO, SAS_AALVO};

static struct {
    int atitude_ok;
    int pitch, rumo, rolagem;
    int marcador_ok[MARCADORES];
    int marcador_p[MARCADORES], marcador_r[MARCADORES];
    int altitude_ok;
    int radar;
    int32_t altitude;
    Numero numeros[NUMEROS];
    int sas, rcs;
    int modo;
    int pagina;
    int sas_modo;
    char sas_cor;
    Numero sas_erro;
    int ap_estado[3];
    Numero ap_valor[3];
    int cursor, escolhida;
    int lei;
    Numero trava;
    int estol;
    int scr, scr_faltam;
    char fase[12], sas_pouso[12], aviso[12];
    Numero pouso[CAMPOS_POUSO];
    int teve_valida;
    uint32_t ultima_valida;
    int tocado;
    uint32_t quando_toque;
} e;

static char linha_atual[MAX_LINHA + 1];
static int tamanho_linha;
static int linha_longa;

static uint32_t agora_quadro;
static int com_sinal;

typedef struct {
    const char *texto;
    Vetor direcao;
    int x, y, visivel;
} NumeroBola;

static NumeroBola numeros_bola[28];
static char textos_bola[28][4];

typedef struct {
    int tipo;
    int x, y;
} MarcadorVisivel;

enum { D_PRO, D_RETRO, D_NRM, D_ANRM, D_RFORA, D_RDENTRO, D_ALVO, D_AALVO, D_MNV, D_FBW };

static MarcadorVisivel visiveis[12];
static int quantos_visiveis;

static int arred14(int v)
{
    return v >= 0 ? (v + 8192) >> 14 : -((-v + 8192) >> 14);
}

static int indice_de(const char *nome, const char *const *nomes, int n)
{
    for (int i = 0; i < n; i++) {
        if (igual(nome, nomes[i]))
            return i;
    }
    return -1;
}

static void copiar(char *destino, const char *origem, int tamanho)
{
    int i = 0;
    for (; i < tamanho - 1 && origem[i]; i++)
        destino[i] = origem[i];
    destino[i] = 0;
}

static int interpretar(char *linha)
{
    char *partes[MAX_PARTES];
    int32_t numeros[MAX_PARTES];
    int n = 0;
    char *nome = linha;
    char *p = linha;
    while (*p && *p != ' ')
        p++;
    if (*p == ' ') {
        *p++ = 0;
        if (*p) {
            partes[n++] = p;
            for (; *p; p++) {
                if (*p == ' ') {
                    *p = 0;
                    if (n == MAX_PARTES)
                        return 0;
                    partes[n++] = p + 1;
                }
            }
        }
    }
    int ok[MAX_PARTES];
    int tudo_numero = n > 0;
    for (int i = 0; i < n; i++) {
        ok[i] = ler_inteiro(partes[i], &numeros[i]);
        tudo_numero = tudo_numero && ok[i];
    }
    int off = n == 1 && igual(partes[0], "OFF");
    int bit = n == 1 && (igual(partes[0], "0") || igual(partes[0], "1"));
    int m = indice_de(nome, nomes_marcadores, MARCADORES);
    int k = indice_de(nome, nomes_numeros, NUMEROS);

    if (igual(nome, "ATT") && n == 3 && tudo_numero) {
        e.atitude_ok = 1;
        e.pitch = numeros[0];
        e.rumo = numeros[1];
        e.rolagem = numeros[2];
    } else if (m >= 0 && off) {
        e.marcador_ok[m] = 0;
    } else if (m >= 0 && n == 2 && tudo_numero) {
        e.marcador_ok[m] = 1;
        e.marcador_p[m] = numeros[0];
        e.marcador_r[m] = numeros[1];
    } else if ((igual(nome, "ALT") || igual(nome, "RAD")) && n == 1 && tudo_numero) {
        e.altitude_ok = 1;
        e.radar = igual(nome, "RAD");
        e.altitude = numeros[0];
    } else if (k >= N_AP && k <= N_DIST && off) {
        e.numeros[k].valido = 0;
    } else if (k >= 0 && n == 1 && tudo_numero) {
        e.numeros[k].valido = 1;
        e.numeros[k].valor = numeros[0];
    } else if ((igual(nome, "SAS") || igual(nome, "RCS")) && bit) {
        *(igual(nome, "SAS") ? &e.sas : &e.rcs) = numeros[0];
    } else if (igual(nome, "PAG") && n == 1 && indice_de(partes[0], nomes_paginas, 4) >= 0) {
        e.pagina = indice_de(partes[0], nomes_paginas, 4);
    } else if (igual(nome, "SASM") && off) {
        e.sas_modo = -1;
        e.sas_cor = 0;
    } else if (igual(nome, "SASM") && n == 2 && (igual(partes[1], "A") || igual(partes[1], "V"))) {
        int modo = indice_de(partes[0], nomes_sas, MODOS_SAS);
        e.sas_modo = modo >= 0 ? modo : -2;
        e.sas_cor = partes[1][0];
    } else if (igual(nome, "SASE") && (off || (n == 1 && tudo_numero))) {
        e.sas_erro.valido = !off;
        e.sas_erro.valor = off ? 0 : numeros[0];
    } else if (igual(nome, "APL") && n == 2 && indice_de(partes[0], nomes_ap, 3) >= 0 && ok[1] && numeros[1] >= 0 && numeros[1] <= 2 && partes[1][1] == 0) {
        e.ap_estado[indice_de(partes[0], nomes_ap, 3)] = numeros[1];
    } else if (igual(nome, "APV") && n == 2 && indice_de(partes[0], nomes_ap, 3) >= 0 && ok[1]) {
        Numero *v = &e.ap_valor[indice_de(partes[0], nomes_ap, 3)];
        v->valido = 1;
        v->valor = numeros[1];
    } else if (igual(nome, "APC") && n == 2 && indice_de(partes[0], nomes_ap, 3) >= 0 && (igual(partes[1], "0") || igual(partes[1], "1"))) {
        e.cursor = indice_de(partes[0], nomes_ap, 3);
        e.escolhida = partes[1][0] == '1';
    } else if (igual(nome, "SCR") && n == 2 && igual(partes[0], "POUSO") && indice_de(partes[1], nomes_scr, 5) >= 0) {
        e.scr = indice_de(partes[1], nomes_scr, 5);
    } else if (igual(nome, "SCR") && n == 3 && igual(partes[0], "POUSO") && (igual(partes[1], "LIGA") || igual(partes[1], "DESL")) && ok[2]) {
        e.scr = indice_de(partes[1], nomes_scr, 7);
        e.scr_faltam = numeros[2];
    } else if (igual(nome, "POU") && off) {
        e.fase[0] = e.sas_pouso[0] = e.aviso[0] = 0;
        for (int i = 0; i < CAMPOS_POUSO; i++)
            e.pouso[i].valido = 0;
    } else if (igual(nome, "POU") && n == 2 && igual(partes[0], "FASE")) {
        copiar(e.fase, partes[1], sizeof(e.fase));
    } else if (igual(nome, "POU") && n == 2 && igual(partes[0], "SAS")) {
        copiar(e.sas_pouso, partes[1], sizeof(e.sas_pouso));
    } else if (igual(nome, "POU") && n == 2 && igual(partes[0], "AVISO")) {
        copiar(e.aviso, partes[1], sizeof(e.aviso));
    } else if (igual(nome, "POU") && n == 2 && indice_de(partes[0], nomes_pouso, CAMPOS_POUSO) >= 0 && (ok[1] || igual(partes[1], "OFF"))) {
        Numero *v = &e.pouso[indice_de(partes[0], nomes_pouso, CAMPOS_POUSO)];
        v->valido = ok[1];
        v->valor = ok[1] ? numeros[1] : 0;
    } else if (igual(nome, "LEI") && n == 1 && indice_de(partes[0], nomes_leis, 4) >= 0) {
        e.lei = indice_de(partes[0], nomes_leis, 4);
    } else if (igual(nome, "ESTOL") && bit) {
        e.estol = numeros[0];
    } else if (igual(nome, "TRAVA") && (off || (n == 1 && tudo_numero))) {
        e.trava.valido = !off;
        e.trava.valor = off ? 0 : numeros[0];
    } else if (igual(nome, "MODO") && n == 1 && indice_de(partes[0], nomes_modos + 1, 3) >= 0) {
        int modo = indice_de(partes[0], nomes_modos + 1, 3) + 1;
        if (modo != e.modo) {
            for (int i = N_VEL; i <= N_DIST; i++)
                e.numeros[i].valido = 0;
            e.marcador_ok[M_PRO] = e.marcador_ok[M_NRM] = e.marcador_ok[M_RDL] = 0;
        }
        e.modo = modo;
    } else {
        return 0;
    }
    return 1;
}

static void executar_linha(uint32_t agora)
{
    char copia[MAX_LINHA + 1];
    copiar(copia, linha_atual, sizeof(copia));
    if (interpretar(linha_atual)) {
        e.ultima_valida = agora;
        e.teve_valida = 1;
    } else {
        char resposta[MAX_LINHA + 6];
        char *p = escrever_texto(resposta, "ERR ");
        escrever_texto(p, copia);
        serial_linha(resposta);
    }
}

void mfd_receber(int byte, uint32_t agora)
{
    if (byte == '\n') {
        linha_atual[tamanho_linha] = 0;
        if (!linha_longa && tamanho_linha > 0)
            executar_linha(agora);
        tamanho_linha = 0;
        linha_longa = 0;
    } else if (byte == '\r') {
        return;
    } else if (tamanho_linha < MAX_LINHA) {
        linha_atual[tamanho_linha++] = (char)byte;
    } else {
        linha_longa = 1;
    }
}

void mfd_iniciar(void)
{
    static const char *const cardeais[4] = {"N", "L", "S", "O"};
    static const int pitches[4] = {60, 30, -30, -60};
    int i = 0;
    for (int h = 0; h < 360; h += 90) {
        for (int k = 0; k < 4; k++, i++) {
            escrever_inteiro(textos_bola[i], pitches[k], 1);
            numeros_bola[i].texto = textos_bola[i];
            navball_direcao(pitches[k] * 10, (h + 6) * 10, &numeros_bola[i].direcao);
        }
    }
    for (int h = 0; h < 360; h += 30, i++) {
        if (h % 90 == 0)
            copiar(textos_bola[i], cardeais[h / 90], 4);
        else
            escrever_inteiro(textos_bola[i], h, 1);
        numeros_bola[i].texto = textos_bola[i];
        navball_direcao(40, h * 10, &numeros_bola[i].direcao);
    }
    e.sas = e.rcs = -1;
    e.sas_modo = -1;
    e.lei = 3;
    e.tocado = BOTAO_NENHUM;
}

static int dentro_retangulo(int x, int y, int rx, int ry, int rl, int ra)
{
    return x >= rx && x < rx + rl && y >= ry && y < ry + ra;
}

static int dentro_botao(int x, int y, int cx, int cy)
{
    return (x - cx) * (x - cx) + (y - cy) * (y - cy) <= RAIO_BOTAO * RAIO_BOTAO;
}

void mfd_tocar(int x, int y, uint32_t agora)
{
    if (e.pagina != PAG_NAV)
        return;
    int botao = BOTAO_NENHUM;
    if (dentro_retangulo(x, y, 20, 82, 80, 32))
        botao = BOTAO_MODO;
    else if (dentro_botao(x, y, 140, 181))
        botao = BOTAO_RCS;
    else if (dentro_botao(x, y, 180, 181))
        botao = BOTAO_SAS;
    if (botao == BOTAO_NENHUM)
        return;
    static const char *const mensagens[3] = {"TOQUE MODO", "TOQUE RCS", "TOQUE SAS"};
    serial_linha(mensagens[botao]);
    e.tocado = botao;
    e.quando_toque = agora;
}

static void na_bola(int x, int y, int *px, int *py)
{
    *px = BOLA_X + arred14(x * RAIO_BOLA);
    *py = BOLA_Y - arred14(y * RAIO_BOLA);
}

static void acrescentar_marcador(int tipo, int pitch, int rumo)
{
    Vetor v;
    int x, y, z;
    navball_direcao(pitch, rumo, &v);
    navball_projetar(&v, &x, &y, &z);
    if (z > 0 && quantos_visiveis < 12) {
        MarcadorVisivel *m = &visiveis[quantos_visiveis++];
        m->tipo = tipo;
        na_bola(x, y, &m->x, &m->y);
    }
}

static void preparar_navball(void)
{
    navball_base(e.pitch, e.rumo, e.rolagem);
    for (int i = 0; i < 28; i++) {
        int x, y, z;
        navball_projetar(&numeros_bola[i].direcao, &x, &y, &z);
        numeros_bola[i].visivel = z > VISIVEL_MIN;
        na_bola(x, y, &numeros_bola[i].x, &numeros_bola[i].y);
    }
    static const int ordem[MARCADORES] = {M_RDL, M_NRM, M_TGT, M_FBW, M_PRO, M_MNV};
    static const int desenho[MARCADORES][2] = {
        [M_RDL] = {D_RFORA, D_RDENTRO},
        [M_NRM] = {D_NRM, D_ANRM},
        [M_TGT] = {D_ALVO, D_AALVO},
        [M_FBW] = {D_FBW, -1},
        [M_PRO] = {D_PRO, D_RETRO},
        [M_MNV] = {D_MNV, -1},
    };
    quantos_visiveis = 0;
    for (int i = 0; i < MARCADORES; i++) {
        int m = ordem[i];
        if (!e.marcador_ok[m])
            continue;
        acrescentar_marcador(desenho[m][0], e.marcador_p[m], e.marcador_r[m]);
        if (desenho[m][1] >= 0)
            acrescentar_marcador(desenho[m][1], -e.marcador_p[m], e.marcador_r[m] + 1800);
    }
}

static void ponto_polar(int cx, int cy, int raio, int decimos, int *x, int *y)
{
    *x = cx + arred14(raio * cosseno10(decimos));
    *y = cy - arred14(raio * seno10(decimos));
}

static void circulo_com_hastes(int cx, int cy, uint16_t cor, const int *angulos, int n, int de, int ate)
{
    circulo(cx, cy, 6, cor, 2);
    for (int i = 0; i < n; i++) {
        int x0, y0, x1, y1;
        ponto_polar(cx, cy, de, angulos[i] * 10, &x0, &y0);
        ponto_polar(cx, cy, ate, angulos[i] * 10, &x1, &y1);
        linha(x0, y0, x1, y1, cor, 2);
    }
}

static void triangulo(int cx, int cy, uint16_t cor, int para_cima, int *pontos)
{
    int s = para_cima ? -1 : 1;
    pontos[0] = cx;
    pontos[1] = cy + 7 * s;
    pontos[2] = cx - 7;
    pontos[3] = cy - 5 * s;
    pontos[4] = cx + 7;
    pontos[5] = cy - 5 * s;
    poligono(pontos, 3, cor, 2);
}

static void desenhar_marcador(int tipo, int cx, int cy)
{
    static const int cruz[4] = {0, 90, 180, 270};
    static const int x_diag[4] = {45, 135, 225, 315};
    static const int tres_pro[3] = {0, 90, 180};
    static const int tres_retro[3] = {90, 225, 315};
    static const int tres_mnv[3] = {90, 210, 330};
    int pontos[6];
    switch (tipo) {
    case D_PRO:
        circulo_com_hastes(cx, cy, COR_PRO, tres_pro, 3, 6, 11);
        circulo(cx, cy, 1, COR_PRO, 0);
        break;
    case D_RETRO:
        circulo_com_hastes(cx, cy, COR_PRO, x_diag, 4, 1, 5);
        circulo_com_hastes(cx, cy, COR_PRO, tres_retro, 3, 6, 11);
        break;
    case D_NRM:
        triangulo(cx, cy, COR_NRM, 1, pontos);
        circulo(cx, cy, 1, COR_NRM, 0);
        break;
    case D_ANRM:
        triangulo(cx, cy, COR_NRM, 0, pontos);
        for (int i = 0; i < 3; i++)
            linha(cx, cy, pontos[2 * i], pontos[2 * i + 1], COR_NRM, 1);
        break;
    case D_RFORA:
        circulo_com_hastes(cx, cy, COR_RDL, x_diag, 4, 6, 11);
        circulo(cx, cy, 1, COR_RDL, 0);
        break;
    case D_RDENTRO:
        circulo_com_hastes(cx, cy, COR_RDL, x_diag, 4, 2, 6);
        break;
    case D_ALVO:
        circulo_com_hastes(cx, cy, COR_TGT, cruz, 4, 6, 11);
        circulo(cx, cy, 1, COR_TGT, 0);
        break;
    case D_AALVO:
        circulo_com_hastes(cx, cy, COR_TGT, x_diag, 4, 1, 5);
        break;
    case D_MNV:
        circulo_com_hastes(cx, cy, COR_MNV, tres_mnv, 3, 6, 11);
        circulo(cx, cy, 3, COR_MNV, 0);
        break;
    case D_FBW:
        for (int sx = -1; sx <= 1; sx += 2) {
            for (int sy = -1; sy <= 1; sy += 2) {
                linha(cx + 8 * sx, cy + 8 * sy, cx + 4 * sx, cy + 8 * sy, COR_FBW, 2);
                linha(cx + 8 * sx, cy + 8 * sy, cx + 8 * sx, cy + 4 * sy, COR_FBW, 2);
            }
        }
        circulo(cx, cy, 1, COR_FBW, 0);
        break;
    }
}

static void simbolo_nave(void)
{
    int cx = BOLA_X, cy = BOLA_Y;
    linha(cx - 24, cy, cx - 9, cy, NAVE, 3);
    linha(cx + 9, cy, cx + 24, cy, NAVE, 3);
    int v[6] = {cx - 9, cy, cx, cy + 7, cx + 9, cy};
    linhas(v, 3, NAVE, 3);
    circulo(cx, cy - 3, 2, NAVE, 0);
}

static void desenhar_navball(void)
{
    circulo(BOLA_X, BOLA_Y, ARO_RAIO, ARO, 0);
    circulo(BOLA_X, BOLA_Y, ARO_RAIO, BORDA, 1);
    if (!com_sinal || !e.atitude_ok) {
        circulo(BOLA_X, BOLA_Y, RAIO_BOLA, BOTAO_APAGADO, 0);
        texto("SEM SINAL", AVISO, &fonte_normal, CENTRO, BOLA_X, BOLA_Y - 20);
        return;
    }
    if (!na_banda(BOLA_Y - ARO_RAIO - 12, BOLA_Y + ARO_RAIO + 12))
        return;
    navball_desenhar(BOLA_X, BOLA_Y);
    for (int i = 0; i < 28; i++) {
        NumeroBola *n = &numeros_bola[i];
        if (!n->visivel)
            continue;
        uint16_t cor = i < 16 ? NUMERO_PITCH : NUMERO_RUMO;
        texto(n->texto, SOMBRA_NUMERO, &fonte_pequena, CENTRO, n->x + 1, n->y + 1);
        texto(n->texto, cor, &fonte_pequena, CENTRO, n->x, n->y);
    }
    for (int i = 0; i < quantos_visiveis; i++)
        desenhar_marcador(visiveis[i].tipo, visiveis[i].x, visiveis[i].y);
    simbolo_nave();
}

static void caixa(int x, int y, int largura, int altura, uint16_t cor, const char *titulo, const char *valor, int destacada)
{
    retangulo(x, y, largura, altura, FUNDO, 0, 4);
    retangulo(x, y, largura, altura, cor, destacada ? 2 : 1, 4);
    texto(titulo, cor, &fonte_pequena, CANTO, x + 5, y + 2);
    texto(valor, TEXTO, &fonte_normal, DIREITA, x + largura - 5, y + 14);
}

static int destacado(int botao)
{
    return e.tocado == botao && agora_quadro - e.quando_toque < DESTAQUE_MS;
}

static void desenhar_caixas(void)
{
    char titulo[12], valor[16];
    if (!na_banda(82, 114))
        return;
    char *p = escrever_texto(titulo, "VEL ");
    escrever_texto(p, e.modo ? nomes_modos[e.modo] : "---");
    formatar_velocidade(valor, com_sinal && e.numeros[N_VEL].valido, e.numeros[N_VEL].valor);
    caixa(20, 82, 80, 32, COR_VEL, titulo, valor, destacado(BOTAO_MODO));
    formatar_distancia(valor, com_sinal && e.altitude_ok, e.altitude);
    caixa(220, 82, 80, 32, COR_ALT, e.altitude_ok && e.radar ? "RADAR" : "ALT", valor, 0);
}

static int y_da_vv(int32_t decimos, int meio, int metade)
{
    int32_t a = decimos < 0 ? -decimos : decimos;
    if (a > 10000)
        a = 10000;
    int32_t base = log2q(10);
    int32_t fracao = (log2q((uint32_t)(10 + a)) - base) * metade / (log2q(10010) - base);
    return decimos >= 0 ? meio - fracao : meio + fracao;
}

static void desenhar_barras(void)
{
    char buf[12];
    int acel_ok = com_sinal && e.numeros[N_ACEL].valido;
    int vv_ok = com_sinal && e.numeros[N_VV].valido;
    int32_t acel = e.numeros[N_ACEL].valor;
    int32_t vv = e.numeros[N_VV].valor;

    preencher(6, 30, 10, 156, ARO);
    if (acel_ok) {
        int32_t limitado = acel < 0 ? 0 : acel > 100 ? 100 : acel;
        int altura = (156 * limitado + 50) / 100;
        preencher(6, 186 - altura, 10, altura, COR_ACEL);
    }
    retangulo(6, 30, 10, 156, BORDA, 1, 0);
    texto("ACEL", ROTULO, &fonte_pequena, CANTO, 2, 4);
    if (acel_ok) {
        char *p = escrever_inteiro(buf, acel, 1);
        escrever_texto(p, "%");
    } else {
        escrever_texto(buf, "---");
    }
    texto(buf, TEXTO, &fonte_pequena, CANTO, 2, 190);

    int meio = 30 + 156 / 2;
    int metade = 156 / 2;
    preencher(304, 30, 10, 156, ARO);
    if (vv_ok) {
        int y = y_da_vv(vv, meio, metade);
        uint16_t cor = vv >= 0 ? VV_SOBE : vv > -100 ? VV_DESCE : VV_DESCE_RAPIDO;
        int topo = y < meio ? y : meio;
        int altura = (y > meio ? y - meio : meio - y) + 1;
        preencher(304, topo, 10, altura, cor);
    }
    retangulo(304, 30, 10, 156, BORDA, 1, 0);
    linha(301, meio, 314, meio, TEXTO, 1);
    static const int marcas[4] = {100, 10, -10, -100};
    for (int i = 0; i < 4; i++) {
        int y = y_da_vv(marcas[i] * 10, meio, metade);
        linha(301, y, 304, y, TRACO, 1);
        char *p = buf;
        *p++ = marcas[i] > 0 ? '+' : '-';
        escrever_inteiro(p, marcas[i] > 0 ? marcas[i] : -marcas[i], 1);
        texto(buf, ROTULO, &fonte_pequena, DIREITA, 300, y - 6);
    }
    texto("V VERT", ROTULO, &fonte_pequena, DIREITA, LARGURA - 2, 4);
}

static void desenhar_botoes(void)
{
    static const int botoes[2] = {BOTAO_RCS, BOTAO_SAS};
    static const int centros[2] = {140, 180};
    static const char *const nomes[2] = {"RCS", "SAS"};
    if (!na_banda(181 - RAIO_BOTAO, 181 + RAIO_BOTAO))
        return;
    for (int i = 0; i < 2; i++) {
        int estado = botoes[i] == BOTAO_SAS ? e.sas : e.rcs;
        int ligado = com_sinal && estado == 1;
        circulo(centros[i], 181, RAIO_BOTAO, ligado ? BOTAO_LIGADO : BOTAO_APAGADO, 0);
        int destaque = destacado(botoes[i]);
        uint16_t borda = destaque ? TEXTO : ligado ? BORDA_LIGADO : BORDA;
        circulo(centros[i], 181, RAIO_BOTAO, borda, destaque ? 2 : 1);
        texto(nomes[i], TEXTO, &fonte_pequena, CENTRO, centros[i], 181);
    }
}

static void desenhar_painel(void)
{
    if (!com_sinal || (e.modo != MODO_ORB && e.modo != MODO_ALVO))
        return;
    if (!na_banda(198, 238))
        return;
    char valor[16], tempo[16];
    retangulo(48, 198, 224, 40, BORDA, 1, 4);
    int y = 201;
    if (e.modo == MODO_ORB) {
        static const char *const rotulos[2] = {"AP", "PE"};
        static const int distancias[2] = {N_AP, N_PE};
        static const int tempos[2] = {N_TAP, N_TPE};
        for (int i = 0; i < 2; i++, y += 17) {
            Numero *d = &e.numeros[distancias[i]];
            Numero *t = &e.numeros[tempos[i]];
            formatar_distancia(valor, d->valido, d->valor);
            formatar_tempo(tempo, t->valido, t->valor);
            texto(rotulos[i], ROTULO, &fonte_pequena, CANTO, 54, y + 2);
            texto(valor, TEXTO, &fonte_normal, DIREITA, 176, y);
            texto(tempo, ROTULO, &fonte_pequena, DIREITA, 267, y + 2);
        }
    } else {
        formatar_distancia(valor, e.numeros[N_DIST].valido, e.numeros[N_DIST].valor);
        texto("DIST", ROTULO, &fonte_pequena, CANTO, 54, y + 2);
        texto(valor, TEXTO, &fonte_normal, DIREITA, 176, y);
    }
}

static int disponivel(int modo)
{
    if (modo == SAS_ALVO || modo == SAS_AALVO)
        return e.marcador_ok[M_TGT];
    if (modo == SAS_MAN)
        return e.marcador_ok[M_MNV];
    return 1;
}

static void marcador_do_modo(int modo, int cx, int cy)
{
    static const int desenhos[MODOS_SAS] = {-1, D_MNV, D_PRO, D_RETRO, D_NRM, D_ANRM, D_RFORA, D_RDENTRO, D_ALVO, D_AALVO};
    if (modo == SAS_ESTAB) {
        circulo(cx, cy, 7, TEXTO, 2);
        linha(cx - 4, cy, cx + 4, cy, TEXTO, 2);
        return;
    }
    desenhar_marcador(desenhos[modo], cx, cy);
}

static void botao_de_modo(int modo, int cx, int cy, int raio)
{
    int escolhido = e.sas_modo == modo;
    uint16_t cor = escolhido ? (e.sas_cor == 'V' ? VERDE : AZUL) : 0;
    if (escolhido)
        circulo(cx, cy, raio + 4, cor, 2);
    circulo(cx, cy, raio, FUNDO_MODO, 0);
    circulo(cx, cy, raio, escolhido ? cor : BORDA, escolhido ? 3 : 1);
    if (disponivel(modo))
        marcador_do_modo(modo, cx, cy);
    else
        texto("--", APAGADO, &fonte_pequena, CENTRO, cx, cy);
}

static void desenhar_pagina_sas(void)
{
    char buf[12];
    int ligado = e.sas == 1;
    texto("SAS", ROTULO, &fonte_pequena, CANTO, 8, 4);
    texto(ligado ? "LIGADO" : "DESLIGADO", ligado ? VERDE : APAGADO, &fonte_normal, CANTO, 8, 17);
    texto("ERRO", ROTULO, &fonte_pequena, DIREITA, 312, 4);
    if (e.sas_erro.valido)
        escrever_decimal(buf, e.sas_erro.valor, 10, 1);
    else
        escrever_texto(buf, "---");
    uint16_t cor_erro = e.sas_cor == 'V' ? VERDE : e.sas_cor == 'A' ? AZUL : APAGADO;
    texto(buf, cor_erro, &fonte_normal, DIREITA, 312, 17);

    circulo(RODA_X, RODA_Y, RODA_RAIO, ARO, 0);
    circulo(RODA_X, RODA_Y, RODA_RAIO, BORDA, 1);
    int xs[6], ys[6];
    for (int i = 0; i < 6; i++) {
        ponto_polar(RODA_X, RODA_Y, RODA_MODOS, -angulos_roda[i] * 10, &xs[i], &ys[i]);
        linha(RODA_X, RODA_Y, xs[i], ys[i], BORDA, 1);
    }
    for (int i = 0; i < 6; i++)
        botao_de_modo(modos_roda[i], xs[i], ys[i], RODA_BOTAO);

    int na_roda = -1;
    for (int i = 0; i < 6; i++) {
        if (modos_roda[i] == e.sas_modo)
            na_roda = i;
    }
    if (ligado && na_roda >= 0) {
        int torto = 0;
        if (e.sas_cor != 'V') {
            torto = e.sas_erro.valido && e.sas_erro.valor ? e.sas_erro.valor : 600;
            if (torto > 600)
                torto = 600;
        }
        int a = angulos_roda[na_roda] * 10 + torto;
        uint16_t cor = e.sas_cor == 'V' ? VERDE : AZUL;
        int v[6];
        ponto_polar(RODA_X, RODA_Y, 9, -(a - 1375), &v[0], &v[1]);
        ponto_polar(RODA_X, RODA_Y, 22, -a, &v[2], &v[3]);
        ponto_polar(RODA_X, RODA_Y, 9, -(a + 1375), &v[4], &v[5]);
        linhas(v, 3, cor, 3);
    }
    circulo(RODA_X, RODA_Y, 3, NAVE, 0);

    for (int i = 0; i < 4; i++) {
        int x = 72 + 46 * i;
        retangulo(x, 190, 40, 28, ARO, 0, 4);
        retangulo(x, 190, 40, 28, BORDA, 1, 4);
        botao_de_modo(modos_faixa[i], x + 20, 204, 11);
    }
    texto("MODO DO SAS", ROTULO, &fonte_pequena, CENTRO, 160, 232);
}

static void valor_ap(char *destino, int linha_ap, const Numero *v)
{
    if (!v->valido) {
        escrever_texto(destino, "---");
    } else if (linha_ap == 0) {
        escrever_inteiro(destino, v->valor, 3);
    } else if (linha_ap == 1) {
        char *p = escrever_inteiro(destino, v->valor, 1);
        escrever_texto(p, " M");
    } else {
        *destino++ = v->valor >= 0 ? '+' : '-';
        char *p = escrever_decimal(destino, v->valor >= 0 ? v->valor : -v->valor, 10, 1);
        escrever_texto(p, " M/S");
    }
}

static void desenhar_pagina_ap(void)
{
    static const char *const estados[3] = {"DESLIGADO", "LIGADO", "ARMADO"};
    static const uint16_t cores_estado[3] = {APAGADO, VERDE, AZUL};
    char buf[20];
    texto("PILOTO AUTOMATICO", ROTULO, &fonte_normal, CENTRO, 160, 12);
    linha(12, 24, 308, 24, BORDA, 1);
    for (int i = 0; i < 3; i++) {
        int y = 46 + i * 44;
        int no_cursor = i == e.cursor;
        int estado = e.ap_estado[i];
        if (no_cursor) {
            int seta[6] = {12, y - 6, 20, y, 12, y + 6};
            linhas(seta, 3, TEXTO, 1);
            if (e.escolhida)
                retangulo(176, y - 15, 130, 30, AMBAR, 2, 3);
            else
                retangulo(24, y - 17, 286, 34, TEXTO, 1, 4);
        }
        texto(rotulos_ap[i], TEXTO, &fonte_media, CANTO, 32, y - 9);
        texto(estados[estado], cores_estado[estado], &fonte_pequena, CANTO, 80, y - 6);
        valor_ap(buf, i, &e.ap_valor[i]);
        texto(buf, no_cursor && e.escolhida ? AMBAR : TEXTO, &fonte_grande, MEIO_DIREITA, 300, y);
    }
    linha(12, 184, 308, 184, BORDA, 1);
    texto("FBW", ROTULO, &fonte_pequena, CANTO, 16, 194);
    texto(textos_leis[e.lei], cores_leis[e.lei], &fonte_normal, CANTO, 48, 192);
    if (e.trava.valido) {
        char *p = escrever_texto(buf, "TRAVA ");
        p = escrever_inteiro(p, e.trava.valor, 1);
        escrever_texto(p, " M");
        texto(buf, VERDE, &fonte_normal, DIREITA, 304, 192);
    } else {
        texto("SEM TRAVA", APAGADO, &fonte_normal, DIREITA, 304, 192);
    }
    texto(e.escolhida ? "GIRAR: VALOR  APERTAR: SAI" : "GIRAR: LINHA  APERTAR: ESCOLHE", ROTULO, &fonte_pequena, CENTRO, 160, 226);
}

static void nave_de_pouso(int x, int pe, int32_t motor, int trem)
{
    if (motor) {
        int comprimento = 6 + 22 * motor / 100;
        int chama[6] = {x - 3, pe - 2, x + 3, pe - 2, x, pe + comprimento};
        poligono(chama, 3, CHAMA, 0);
        int meio[6] = {x - 1, pe - 2, x + 1, pe - 2, x, pe + comprimento * 55 / 100};
        poligono(meio, 3, CHAMA_MEIO, 0);
    }
    preencher(x - 3, pe - 38, 7, 34, CORPO_NAVE);
    retangulo(x - 3, pe - 38, 7, 34, APAGADO, 1, 0);
    linha(x - 3, pe - 22, x + 3, pe - 22, APAGADO, 1);
    int nariz[6] = {x - 3, pe - 38, x + 3, pe - 38, x, pe - 45};
    poligono(nariz, 3, CORPO_NAVE, 0);
    preencher(x - 2, pe - 4, 5, 3, APAGADO);
    for (int lado = -1; lado <= 1; lado += 2) {
        if (trem)
            linha(x + 3 * lado, pe - 12, x + 9 * lado, pe, TEXTO, 1);
        else
            linha(x + 3 * lado, pe - 12, x + 5 * lado, pe - 3, TEXTO, 1);
    }
}

static void desenhar_pagina_pouso(void)
{
    static const char *const nomes_avisos[3] = {"EMPUXO", "MOTOR", "NARIZ"};
    static const char *const textos_avisos[3] = {"EMPUXO INSUFICIENTE", "SEM MOTOR ATIVO", "NARIZ LONGE DA VERTICAL"};
    Numero *p = e.pouso;
    char buf[24];

    elipse(-160, POUSO_CHAO - 8, 640, 200, CHAO_POUSO, 0);
    elipse(160 - 38, POUSO_CHAO + 4 - 8, 76, 16, ALVO_POUSO, 3);
    elipse(160 - 22, POUSO_CHAO + 4 - 4, 44, 9, ALVO_POUSO, 3);
    circulo(160, POUSO_CHAO + 4, 2, ALVO_POUSO, 0);

    if (p[P_ALT].valido) {
        int32_t a = p[P_ALT].valor < 0 ? 0 : p[P_ALT].valor > 100000 ? 100000 : p[P_ALT].valor;
        int32_t base = log2q(10);
        int32_t subida = (log2q((uint32_t)(10 + a)) - base) * (POUSO_CHAO + 4 - POUSO_TOPO) / (log2q(100010) - base);
        int pe = POUSO_CHAO + 4 - subida;
        for (int y = pe + 4; y < POUSO_CHAO; y += 8)
            linha(160, y, 160, y + 4 < POUSO_CHAO ? y + 4 : POUSO_CHAO, TRACEJADO, 1);
        int trem = igual(e.fase, "QUEIMA") || igual(e.fase, "TOQUE") || igual(e.fase, "POUSADA");
        nave_de_pouso(160, pe, p[P_MOTOR].valido ? p[P_MOTOR].valor : 0, trem);
    }

    char alt[16], vel[16], twr[16];
    if (!p[P_ALT].valido) {
        escrever_texto(alt, "---");
    } else if (p[P_ALT].valor < 1000) {
        char *q = escrever_decimal(alt, p[P_ALT].valor, 10, 1);
        escrever_texto(q, " m");
    } else {
        formatar_distancia(alt, 1, (p[P_ALT].valor + 5) / 10);
    }
    if (p[P_VV].valido) {
        char *q = escrever_decimal(vel, p[P_VV].valor < 0 ? -p[P_VV].valor : p[P_VV].valor, 10, 1);
        escrever_texto(q, " m/s");
    } else {
        escrever_texto(vel, "---");
    }
    if (p[P_TWR].valido)
        escrever_decimal(twr, p[P_TWR].valor, 100, 2);
    else
        escrever_texto(twr, "---");
    const char *rotulos_esq[3] = {"ALT", "VEL", "TWR"};
    const char *valores_esq[3] = {alt, vel, twr};
    for (int i = 0; i < 3; i++) {
        texto(rotulos_esq[i], ROTULO, &fonte_normal, CANTO, 8, 6 + i * 15);
        texto(valores_esq[i], VERDE, &fonte_normal, CANTO, 44, 6 + i * 15);
    }

    char motor[12], incl[12];
    if (p[P_MOTOR].valido) {
        char *q = escrever_inteiro(motor, p[P_MOTOR].valor, 1);
        escrever_texto(q, "%");
    } else {
        escrever_texto(motor, "---");
    }
    if (p[P_INCL].valido) {
        char *q = escrever_inteiro(incl, p[P_INCL].valor, 1);
        escrever_texto(q, " GR");
    } else {
        escrever_texto(incl, "---");
    }
    const char *rotulos_dir[3] = {"SAS", "MOTOR", "INCL"};
    const char *valores_dir[3] = {e.sas_pouso[0] ? e.sas_pouso : "---", motor, incl};
    for (int i = 0; i < 3; i++) {
        texto(rotulos_dir[i], ROTULO, &fonte_normal, DIREITA, 258, 6 + i * 15);
        texto(valores_dir[i], VERDE, &fonte_normal, DIREITA, 312, 6 + i * 15);
    }

    int aviso = indice_de(e.aviso, nomes_avisos, 3);
    if (aviso >= 0 && (agora_quadro / 500u) % 2u == 0)
        texto(textos_avisos[aviso], AVISO, &fonte_pequena, CENTRO, 160, 56);

    if (e.scr == SCR_LIGA || e.scr == SCR_DESL) {
        retangulo(90, 80, 140, 56, FUNDO, 0, 6);
        retangulo(90, 80, 140, 56, AMBAR, 2, 6);
        char *q = escrever_texto(buf, "SEGURE ");
        q = escrever_inteiro(q, e.scr_faltam, 1);
        escrever_texto(q, " S");
        texto(buf, AMBAR, &fonte_grande, CENTRO, 160, 100);
        texto(e.scr == SCR_LIGA ? "PARA POUSAR" : "PARA ABORTAR", AMBAR, &fonte_pequena, CENTRO, 160, 122);
    }

    const char *fase;
    uint16_t cor;
    if (e.scr == SCR_FIM) {
        fase = "POUSADA";
        cor = VERDE;
    } else if (e.scr == SCR_ABORT) {
        fase = "ABORTADO";
        cor = AVISO;
    } else if (e.scr == SCR_FALHA) {
        fase = "FALHOU";
        cor = AVISO;
    } else if (e.scr == SCR_LIGA) {
        fase = "ARMANDO";
        cor = AMBAR;
    } else if (igual(e.fase, "QUEDA")) {
        fase = "QUEDA";
        cor = AZUL;
    } else if (igual(e.fase, "QUEIMA") || igual(e.fase, "TOQUE") || igual(e.fase, "POUSADA")) {
        fase = e.fase;
        cor = VERDE;
    } else if (e.scr == SCR_ATIVO || e.scr == SCR_DESL) {
        fase = "LIGANDO";
        cor = AZUL;
    } else {
        fase = "PARADO";
        cor = APAGADO;
    }
    circulo(26, 212, 16, cor, 2);
    circulo(26, 212, 7, cor, 2);
    circulo(26, 212, 2, cor, 0);
    linha(37, 212, 45, 212, cor, 2);
    linha(15, 212, 7, 212, cor, 2);
    linha(26, 223, 26, 231, cor, 2);
    linha(26, 201, 26, 193, cor, 2);
    texto(fase, cor, &fonte_normal, CANTO, 48, 203);
    linha(46, 222, 118, 222, cor, 1);

    texto("FREADA", ROTULO, &fonte_pequena, CANTO, 212, 204);
    Numero *f = &p[P_FREADA];
    if (!f->valido) {
        escrever_texto(buf, "---");
    } else if (f->valor < 999) {
        char *q = escrever_inteiro(buf, f->valor, 1);
        escrever_texto(q, "%");
    } else {
        escrever_texto(buf, "> 100%");
    }
    texto(buf, f->valido && f->valor > 100 ? AVISO : TEXTO, &fonte_normal, DIREITA, 312, 202);
    preencher(212, 220, 100, 8, ARO);
    if (f->valido) {
        int32_t largura = f->valor > 100 ? 100 : f->valor < 0 ? 0 : f->valor;
        uint16_t cor_barra = f->valor > 100 ? AVISO : !igual(e.fase, "QUEDA") ? VERDE : AZUL;
        preencher(212, 220, largura, 8, cor_barra);
    }
    retangulo(212, 220, 100, 8, BORDA, 1, 0);
    if (p[P_IGN].valido) {
        int x = 212 + p[P_IGN].valor;
        linha(x, 217, x, 230, AMBAR, 2);
    }
}

static void cena(void)
{
    preencher(0, banda_y0, LARGURA, BANDA, FUNDO);
    if (com_sinal && e.pagina == PAG_SAS) {
        desenhar_pagina_sas();
    } else if (com_sinal && e.pagina == PAG_AP) {
        desenhar_pagina_ap();
    } else if (com_sinal && e.pagina == PAG_POUSO) {
        desenhar_pagina_pouso();
    } else {
        desenhar_navball();
        desenhar_caixas();
        desenhar_barras();
        desenhar_botoes();
        desenhar_painel();
    }
}

void mfd_desenhar(uint32_t agora)
{
    agora_quadro = agora;
    com_sinal = e.teve_valida && agora - e.ultima_valida < SEM_SINAL_MS;
    if (com_sinal && e.atitude_ok && e.pagina == PAG_NAV)
        preparar_navball();
    desenhar_quadro(cena);
}
