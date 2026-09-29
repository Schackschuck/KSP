#ifndef LCD_H
#define LCD_H

#include <stdint.h>

#define LCD_LARGURA 320
#define LCD_ALTURA 240

void lcd_iniciar(void);
uint16_t lcd_id(void);
void lcd_orientacao(uint8_t valor);
void lcd_luz(int ligada);
void lcd_janela(int x0, int y0, int x1, int y1);
void lcd_pixels(const uint16_t *pixels, int quantos);
void lcd_preencher(uint16_t cor, int quantos);

#endif
