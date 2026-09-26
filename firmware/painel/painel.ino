// Firmware do painel: Arduino Mega 2560, protocolo v0 (texto)
//
// Fase 2: botões STAGE e ABORT, chaves de SAS, RCS, trem de pouso, luzes e
// freios, um LED de estado para cada chave, e o LCD 20x4 da fase 1.
//
// Montagem (tudo direto nos pinos do Mega; a pinagem completa, com desenho,
// está em docs/fase2.md):
//   Botões e chaves:  pino ──[contato]── GND      sem resistor: usa o pull-up interno
//     STAGE 2    ABORT 3    SAS 22    RCS 24    GEAR 26    LIGHTS 28    BRAKES 30
//   LEDs:             pino ──[220 Ω]──(+)LED(−)── GND
//     SAS 8      RCS 9      GEAR 10   LIGHTS 11   BRAKES 12
//   LCD I2C:          SDA → pino 20   SCL → pino 21   VCC → 5V   GND → GND
//
// Biblioteca necessária (Arduino IDE → Library Manager):
//   "LiquidCrystal I2C", de Frank de Brabander
//
// Protocolo v0: texto, 115200 baud, uma mensagem por linha terminada em '\n'.
// A especificação completa está em docs/protocolo.md.
//   Painel → ponte:  READY | BTN <nome> <0|1> | SW <nome> <0|1> | ERR <linha>
//   Ponte → painel:  <nome do LED> <0|1> (ex.: SAS 1, GEAR 0) | ALT <metros>
//
// Teste sem o KSP, pelo Serial Monitor (115200 baud, final de linha em
// "Nova linha"): mexa nas chaves e botões e veja as mensagens; digite
// "RCS 1", "ALT 12345"... e veja os LEDs e o LCD. Sem mensagens por 1 segundo,
// o LCD mostra "sem sinal" e os LEDs apagam.
//
// Lembre do princípio do projeto: o painel NÃO SABE QUE O KSP EXISTE. Ele
// avisa que uma chave mudou, acende LEDs e mostra um número. Os nomes (SAS,
// GEAR...) são só etiquetas; quem dá sentido a eles é a ponte (bridge/ponte.py).
//
// O que mudou em relação à fase 1: os controles saíram de variáveis soltas e
// viraram TABELAS (ENTRADAS e LEDS, logo abaixo). O código percorre as tabelas
// e não conhece nenhum controle pelo nome. Para acrescentar uma chave ou um
// LED, basta uma linha na tabela (e o tratamento correspondente na ponte).

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ================================================================ config =====

// Endereço I2C do LCD: rode o passo4_i2c_scanner para descobrir o seu.
// Os mais comuns são 0x27 e 0x3F.
const uint8_t LCD_ENDERECO = 0x27;
const uint8_t LCD_COLUNAS = 20;
const uint8_t LCD_LINHAS = 4;

const unsigned long DEBOUNCE_MS = 20;

// A ponte manda a altitude 10 vezes por segundo. Se passar 1 segundo sem
// nenhuma mensagem, a ponte caiu, o jogo fechou ou o cabo soltou.
const unsigned long TIMEOUT_SINAL_MS = 1000;

// Redesenhar o LCD no máximo 5 vezes por segundo (a explicação está em
// atualizarLcd()).
const unsigned long INTERVALO_LCD_MS = 200;

// Estado "não sei" de um LED: antes da primeira mensagem ou sem sinal.
const int8_t DESCONHECIDO = -1;

// ======================================================== tabela: entradas ===
//
// Botões e chaves são lidos do mesmo jeito: contato entre o pino e o GND, com
// o pull-up interno. Contato fechado (pino em LOW) vira 1 na mensagem.
//   - Botão (BTN): 1 = apertado, 0 = solto.
//   - Chave (SW): 1 = ligada, 0 = desligada. Monte a chave de modo que "para
//     cima" feche o contato.
// A única diferença entre os dois é a palavra na mensagem: é a ponte que decide
// que um botão dispara uma ação e uma chave define um estado.

struct Entrada {
  const char *tipo;   // "BTN" ou "SW"
  const char *nome;
  uint8_t pino;
};

// Os pinos 0 e 1 (serial da USB), 20 e 21 (I2C do LCD) e 50 a 53 (SPI, para
// os shift registers do futuro) ficam de fora. As chaves usam só pinos pares
// da barra dupla (22, 24...) para ficarem todas na mesma fileira.
const Entrada ENTRADAS[] = {
  {"BTN", "STAGE", 2},
  {"BTN", "ABORT", 3},
  {"SW", "SAS", 22},
  {"SW", "RCS", 24},
  {"SW", "GEAR", 26},
  {"SW", "LIGHTS", 28},
  {"SW", "BRAKES", 30},
};

// sizeof(tabela) / sizeof(um item) = número de itens. Calculado pelo
// compilador: acrescentar uma linha na tabela não exige mudar mais nada.
const uint8_t NUM_ENTRADAS = sizeof(ENTRADAS) / sizeof(ENTRADAS[0]);

// ============================================================ tabela: LEDs ===
//
// Cada LED mostra o estado de um sistema NO JOGO, não a posição da chave: se o
// jogo desligar o SAS sozinho, o LED apaga, mesmo com a chave para cima.

struct Led {
  const char *nome;   // o mesmo nome da mensagem que vem da ponte ("SAS 1")
  uint8_t pino;
};

const Led LEDS[] = {
  {"SAS", 8},
  {"RCS", 9},
  {"GEAR", 10},
  {"LIGHTS", 11},
  {"BRAKES", 12},
};

const uint8_t NUM_LEDS = sizeof(LEDS) / sizeof(LEDS[0]);

const int8_t NAO_ENCONTRADO = -1;

// ================================================================ estado =====
//
// As tabelas acima são constantes: dizem o que existe e onde está ligado. O
// que muda durante o funcionamento fica aqui, em vetores do mesmo tamanho: o
// item i de cada vetor pertence ao item i da tabela.

// Debounce de cada entrada (igual ao passo 2), preenchido no setup().
bool entradaEstavel[NUM_ENTRADAS];
bool entradaUltimaLeitura[NUM_ENTRADAS];
unsigned long entradaInstanteMudanca[NUM_ENTRADAS];

// Estado de cada LED: -1 = desconhecido, 0 = apagado, 1 = aceso.
int8_t estadoLed[NUM_LEDS];

// O LCD mostra o SAS na linha 2: posição dele na tabela LEDS (setup()).
int8_t indiceSas = NAO_ENCONTRADO;

long altitude = 0;               // em metros; long = inteiro de 32 bits com sinal
bool altitudeConhecida = false;

// Sinal da ponte.
bool comSinal = false;
unsigned long ultimaMensagem = 0;   // instante da última mensagem válida

// "Esta linha do LCD precisa ser redesenhada?" Uma bandeira por linha.
bool redesenharAltitude = true;
bool redesenharSas = true;
bool redesenharSinal = true;
unsigned long ultimoDesenho = 0;

// Linha da serial sendo montada (igual ao passo 3).
const uint8_t TAMANHO_LINHA = 32;
char linha[TAMANHO_LINHA];
uint8_t tamanhoLinha = 0;
bool linhaGrandeDemais = false;

// O objeto que conversa com o LCD pelo I2C.
LiquidCrystal_I2C lcd(LCD_ENDERECO, LCD_COLUNAS, LCD_LINHAS);

// ======================================================= botões e chaves =====

// Mesmo debounce do passo 2, agora para cada item da tabela. O painel só
// avisa o que mudou; quem decide o que fazer é a ponte.
void lerEntrada(uint8_t i) {
  bool leitura = digitalRead(ENTRADAS[i].pino);
  if (leitura != entradaUltimaLeitura[i]) {
    entradaUltimaLeitura[i] = leitura;
    entradaInstanteMudanca[i] = millis();
  }
  if (leitura != entradaEstavel[i] && millis() - entradaInstanteMudanca[i] >= DEBOUNCE_MS) {
    entradaEstavel[i] = leitura;
    // Ex.: "SW GEAR 1". Pull-up: contato fechado = LOW = 1.
    Serial.print(ENTRADAS[i].tipo);
    Serial.print(' ');
    Serial.print(ENTRADAS[i].nome);
    Serial.println(leitura == LOW ? F(" 1") : F(" 0"));
  }
}

void lerEntradas() {
  for (uint8_t i = 0; i < NUM_ENTRADAS; i++) {
    lerEntrada(i);
  }
}

// ================================================================== LEDs =====

void mudarLed(uint8_t i, int8_t estado) {
  if (estado == estadoLed[i]) {
    return;
  }
  estadoLed[i] = estado;
  // O LED é atualizado na hora: é só um pino, custa quase nada.
  // Desconhecido fica apagado, igual a desligado.
  digitalWrite(LEDS[i].pino, estado == 1 ? HIGH : LOW);
  if (i == indiceSas) {
    redesenharSas = true;   // o LCD fica para depois (é lento)
  }
}

// Procura na tabela o LED com esse nome e devolve a posição dele, ou
// NAO_ENCONTRADO. 'tamanho' = quantos caracteres do texto formam o nome (o
// texto vem da linha recebida, e o nome termina no espaço, não num '\0').
int8_t procurarLed(const char *nome, size_t tamanho) {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    if (strlen(LEDS[i].nome) == tamanho && strncmp(LEDS[i].nome, nome, tamanho) == 0) {
      return i;
    }
  }
  return NAO_ENCONTRADO;
}

// ========================================================= serial → estado ===

bool lerInteiro(const char *texto, long *valor) {
  char *fim;
  *valor = strtol(texto, &fim, 10);
  return fim != texto && *fim == '\0';
}

// Chamada a cada mensagem válida: renova o sinal.
void registrarMensagem() {
  ultimaMensagem = millis();
  if (!comSinal) {
    comSinal = true;
    redesenharSinal = true;
  }
}

// Toda mensagem da ponte tem a forma "NOME VALOR".
void processarLinha(const char *texto) {
  const char *espaco = strchr(texto, ' ');
  long valor;

  if (espaco != nullptr && lerInteiro(espaco + 1, &valor)) {
    size_t tamanhoNome = espaco - texto;

    if (tamanhoNome == 3 && strncmp(texto, "ALT", 3) == 0) {
      registrarMensagem();
      // Só marca para redesenhar se o número mudou de verdade.
      if (!altitudeConhecida || valor != altitude) {
        altitude = valor;
        altitudeConhecida = true;
        redesenharAltitude = true;
      }
      return;
    }

    int8_t led = procurarLed(texto, tamanhoNome);
    if (led != NAO_ENCONTRADO && (valor == 0 || valor == 1)) {
      registrarMensagem();
      mudarLed(led, valor);
      return;
    }
  }

  Serial.print(F("ERR "));
  Serial.println(texto);
}

void lerSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      linha[tamanhoLinha] = '\0';
      if (tamanhoLinha > 0 && !linhaGrandeDemais) {
        processarLinha(linha);
      }
      tamanhoLinha = 0;
      linhaGrandeDemais = false;
    } else if (tamanhoLinha < TAMANHO_LINHA - 1) {
      linha[tamanhoLinha] = c;
      tamanhoLinha++;
    } else {
      linhaGrandeDemais = true;
    }
  }
}

// ================================================================= sinal =====

// Se a ponte ficou quieta por TIMEOUT_SINAL_MS, o que o painel sabe ficou
// velho. Em vez de mostrar estados e uma altitude que talvez nem existam
// mais, o painel "esquece" os dados e mostra que está sem sinal.
void verificarSinal() {
  if (comSinal && millis() - ultimaMensagem >= TIMEOUT_SINAL_MS) {
    comSinal = false;
    for (uint8_t i = 0; i < NUM_LEDS; i++) {
      mudarLed(i, DESCONHECIDO);
    }
    altitudeConhecida = false;
    redesenharSinal = true;
    redesenharAltitude = true;
  }
}

// =================================================================== LCD =====

// Escreve 'texto' na linha 'numeroLinha' do LCD e completa com espaços até a
// última coluna. Os espaços apagam o que sobrou do texto anterior (ex.: de
// "desligado" para "ligado" sobrariam letras) sem usar lcd.clear(). O clear()
// apaga a tela inteira, e redesenhar tudo toda hora faz o display piscar.
void escreverLinha(uint8_t numeroLinha, const char *texto) {
  lcd.setCursor(0, numeroLinha);   // coluna 0, linha numeroLinha (a primeira é a 0)
  uint8_t coluna = 0;
  while (texto[coluna] != '\0' && coluna < LCD_COLUNAS) {
    lcd.write(texto[coluna]);
    coluna++;
  }
  while (coluna < LCD_COLUNAS) {
    lcd.write(' ');
    coluna++;
  }
}

// Escreve 'valor' com pontos separando os milhares em 'saida'.
// Ex.: 1234567 → "1.234.567", -5 → "-5". 'saida' precisa de 15 posições.
//
// Os dígitos saem do último para o primeiro (valor % 10 dá o último dígito;
// valor / 10 o remove), então são montados ao contrário e invertidos no fim.
void formatarMilhares(long valor, char *saida) {
  char invertido[15];
  uint8_t n = 0;

  // Trabalha com o valor sem sinal; o '-' entra no fim. (A conta
  // "0UL - valor" funciona até para o menor long possível, onde "-valor" daria
  // um número que não cabe.)
  unsigned long resto = valor < 0 ? 0UL - (unsigned long)valor : (unsigned long)valor;
  uint8_t digitosNoGrupo = 0;

  do {
    if (digitosNoGrupo == 3) {   // a cada 3 dígitos, um ponto
      invertido[n++] = '.';
      digitosNoGrupo = 0;
    }
    invertido[n++] = '0' + (resto % 10);   // '0' + 7 = '7' (a tabela ASCII é sequencial)
    resto /= 10;
    digitosNoGrupo++;
  } while (resto > 0);   // do/while: o valor 0 ainda escreve um "0"

  if (valor < 0) {
    invertido[n++] = '-';
  }

  // Desinverte para a saída.
  uint8_t i = 0;
  while (n > 0) {
    saida[i++] = invertido[--n];
  }
  saida[i] = '\0';
}

void desenharAltitude() {
  char numero[15];
  if (altitudeConhecida) {
    formatarMilhares(altitude, numero);
  } else {
    strcpy(numero, "--");
  }
  // snprintf monta texto formatado num vetor, sem nunca passar do tamanho
  // dado. "%13s" = texto alinhado à direita num espaço de 13 colunas, para o
  // número não "dançar" na tela quando muda de tamanho.
  // "Alt: " (5) + 13 + " m" (2) = 20 colunas, exatamente a largura do LCD.
  char texto[LCD_COLUNAS + 1];   // + 1 para o '\0'
  snprintf(texto, sizeof(texto), "Alt: %13s m", numero);
  escreverLinha(1, texto);
}

void desenharSas() {
  // Se alguém tirar o SAS da tabela, a linha só mostra "--" em vez de travar.
  int8_t estado = indiceSas != NAO_ENCONTRADO ? estadoLed[indiceSas] : DESCONHECIDO;
  if (estado == 1) {
    escreverLinha(2, "SAS: ligado");
  } else if (estado == 0) {
    escreverLinha(2, "SAS: desligado");
  } else {
    escreverLinha(2, "SAS: --");
  }
}

void desenharSinal() {
  // O LCD não tem acentos (a tabela de caracteres dele é quase só ASCII).
  escreverLinha(3, comSinal ? "Ponte: OK" : "Ponte: sem sinal");
}

// Redesenha só as linhas marcadas, e no máximo a cada INTERVALO_LCD_MS.
//
// Por que limitar? Cada caractere enviado ao LCD pelo I2C leva em torno de
// 1 ms, e uma linha inteira leva uns 20 ms. Nesse tempo o laço não lê as
// entradas nem a serial. Redesenhando só o que mudou, e no máximo 5 vezes por
// segundo, o LCD ocupa uma fração pequena do tempo e o resto fica livre. Mais
// que isso o olho nem acompanha.
void atualizarLcd() {
  if (millis() - ultimoDesenho < INTERVALO_LCD_MS) {
    return;
  }
  ultimoDesenho = millis();

  if (redesenharAltitude) {
    desenharAltitude();
    redesenharAltitude = false;
  }
  if (redesenharSas) {
    desenharSas();
    redesenharSas = false;
  }
  if (redesenharSinal) {
    desenharSinal();
    redesenharSinal = false;
  }
}

// ============================================================ setup/loop =====

void setup() {
  Serial.begin(115200);

  // A posição inicial das chaves vira o estado "estável" SEM gerar mensagem:
  // o painel só avisa quando alguém mexe. Assim, ligar o painel ou reiniciar
  // a ponte nunca muda nada no jogo sozinho.
  for (uint8_t i = 0; i < NUM_ENTRADAS; i++) {
    pinMode(ENTRADAS[i].pino, INPUT_PULLUP);
    entradaEstavel[i] = digitalRead(ENTRADAS[i].pino);
    entradaUltimaLeitura[i] = entradaEstavel[i];
    entradaInstanteMudanca[i] = millis();
  }

  // Os LEDs começam apagados e em "desconhecido": o painel ainda não sabe
  // nada do jogo.
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    pinMode(LEDS[i].pino, OUTPUT);
    digitalWrite(LEDS[i].pino, LOW);
    estadoLed[i] = DESCONHECIDO;
  }
  indiceSas = procurarLed("SAS", 3);

  lcd.init();        // inicializa o controlador do LCD (e o I2C)
  lcd.backlight();   // liga a luz de fundo
  escreverLinha(0, "KSP Cockpit");   // linha 0 é fixa, desenhada uma vez só
  // As linhas 1 a 3 já estão marcadas para desenhar ("--" e "sem sinal").

  Serial.println(F("READY"));
}

// O laço inteiro: cada função faz um pedacinho e devolve o controle na hora.
// Nenhuma espera por nada.
void loop() {
  lerEntradas();      // entrada: botões e chaves → mensagens para a ponte
  lerSerial();        // entrada: mensagens da ponte → estado
  verificarSinal();   // a ponte ainda está falando?
  atualizarLcd();     // saída: estado → LCD
}
