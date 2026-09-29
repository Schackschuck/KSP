#include "ajuste.h"
#include "desenho.h"
#include "lcd.h"
#include "mfd.h"
#include "navball.h"
#include "relogio.h"
#include "serial.h"
#include "texto.h"
#include "toque.h"

#define INTERVALO_QUADRO_MS 40u
#define INTERVALO_TOQUE_MS 30u
#define TELA_INICIAL_MS 1500u

static void cena_inicio(void)
{
    char buf[24];
    preencher(0, banda_y0, LARGURA, BANDA, RGB(6, 10, 22));
    texto("KSP", RGB(255, 140, 0), &fonte_grande, CENTRO, 160, 80);
    texto("TELA MULTIFUNCAO", RGB(240, 240, 240), &fonte_media, CENTRO, 160, 110);
    char *p = escrever_texto(buf, "CONTROLADOR ");
    escrever_hex(p, lcd_id(), 4);
    texto(buf, RGB(130, 150, 200), &fonte_pequena, CENTRO, 160, 140);
    texto("SEGURE A TELA PARA AJUSTAR", RGB(130, 150, 200), &fonte_pequena, CENTRO, 160, 200);
}

int main(void)
{
    relogio_iniciar();
    lcd_iniciar();
    toque_iniciar();
    navball_iniciar();
    serial_iniciar();

    for (int i = 0; i < 3; i++) {
        lcd_luz(1);
        esperar_ms(150);
        lcd_luz(0);
        esperar_ms(150);
    }
    int salvo = ajuste_carregar();
    desenhar_quadro(cena_inicio);
    lcd_luz(1);
    esperar_ms(TELA_INICIAL_MS);
    if (!salvo || ajuste_pedido())
        ajuste_executar(!salvo);

    mfd_iniciar();
    serial_descartar();
    serial_linha("READY");
    char id[8];
    char *p = escrever_texto(id, "ID ");
    escrever_hex(p, lcd_id(), 4);
    serial_linha(id);

    uint32_t ultimo_quadro = relogio_ms();
    uint32_t ultimo_toque = ultimo_quadro;
    int apertado = 0;
    int soltos = 0;
    for (;;) {
        uint32_t agora = relogio_ms();
        int byte;
        while ((byte = serial_ler()) >= 0)
            mfd_receber(byte, agora);

        if (agora - ultimo_toque >= INTERVALO_TOQUE_MS) {
            ultimo_toque = agora;
            int u, v, x, y;
            if (toque_ler(&u, &v)) {
                soltos = 0;
                if (!apertado && ajuste_mapear(u, v, &x, &y))
                    mfd_tocar(x, y, agora);
                apertado = 1;
            } else if (++soltos >= 2) {
                apertado = 0;
            }
        }

        if (agora - ultimo_quadro >= INTERVALO_QUADRO_MS) {
            ultimo_quadro = agora;
            mfd_desenhar(agora);
        }
    }
}
