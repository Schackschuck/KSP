// Fase 1 — Passo 4 (antes do LCD): descobrir o endereço I2C do display
//
// Montagem do LCD (módulo I2C soldado atrás do display):
//   GND → GND    VCC → 5V    SDA → pino 20    SCL → pino 21
//
// ATENÇÃO: no Mega o I2C fica nos pinos 20 (SDA) e 21 (SCL). Os tutoriais de
// Arduino Uno usam A4 e A5, e no Mega isso não funciona.
//
// Teste: abra o Serial Monitor em 115200 baud. Deve aparecer um endereço,
// normalmente 0x27 ou 0x3F. Anote e use em LCD_ENDERECO, no painel.ino.
//
// -----------------------------------------------------------------------------
// Como funciona o I2C
// -----------------------------------------------------------------------------
// I2C é um barramento: vários dispositivos compartilham os mesmos dois fios
// (SDA = dados, SCL = relógio). Cada dispositivo tem um endereço de 7 bits
// (1 a 127). Para falar com um deles, o Mega manda o endereço no barramento,
// e só o dono daquele endereço responde, com um "ACK" (reconhecimento).
//
// Este sketch chama todos os endereços, um por um, e mostra quem respondeu.
//
// O módulo atrás do LCD é um PCF8574: um chip que recebe um byte pelo I2C e o
// coloca em 8 pinos de saída, que por sua vez comandam o LCD. Por isso o
// display, que normalmente precisaria de 6 fios de dados, usa só 2.
//
// Se nada aparecer:
//   - confira SDA/SCL nos pinos 20/21 (e não trocados entre si);
//   - confira o VCC no 5V;
//   - gire o trimpot azul do módulo: o endereço aparece mesmo com o contraste
//     errado, mas se o endereço aparecer e o LCD continuar "em branco" no
//     painel.ino, o problema é o contraste.

#include <Wire.h>   // biblioteca do I2C, já vem com a Arduino IDE

void procurarDispositivos() {
  Serial.println(F("Procurando dispositivos I2C..."));
  uint8_t encontrados = 0;

  for (uint8_t endereco = 1; endereco < 127; endereco++) {
    Wire.beginTransmission(endereco);
    // endTransmission() devolve 0 quando alguém respondeu (ACK) naquele endereço.
    if (Wire.endTransmission() == 0) {
      Serial.print(F("  Encontrado: 0x"));
      if (endereco < 16) {
        Serial.print('0');   // escreve 0x0A em vez de 0xA
      }
      Serial.println(endereco, HEX);
      encontrados++;
    }
  }

  if (encontrados == 0) {
    Serial.println(F("  Nenhum dispositivo. Confira a ligacao (SDA=20, SCL=21)."));
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  Wire.begin();   // o Mega é o "mestre" do barramento
}

void loop() {
  procurarDispositivos();
  // Aqui o delay() não atrapalha nada: este sketch é uma ferramenta que só
  // faz uma coisa. A regra "nada de delay()" vale quando o laço tem mais de
  // uma tarefa. Entender o porquê da regra vale mais que decorar a regra.
  delay(3000);
}
