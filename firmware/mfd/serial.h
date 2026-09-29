#ifndef SERIAL_H
#define SERIAL_H

void serial_iniciar(void);
int serial_ler(void);
void serial_descartar(void);
void serial_enviar(const char *texto);
void serial_linha(const char *texto);

#endif
