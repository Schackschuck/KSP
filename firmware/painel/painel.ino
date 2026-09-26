// Firmware do painel: Arduino Mega 2560, protocolo v0 (texto)
//
// Este é o passo 4 da fase 1 e o firmware "de verdade" do painel. Ele junta
// o botão (passo 2), os comandos pela serial (passo 3) e o LCD 20x4.
//
// Montagem:
//   Botão STAGE:  pino 2 ──[botão]── GND
//   LED SAS:      pino 8 ──[220 Ω]──(+)LED(−)── GND
//   LCD I2C:      SDA → pino 20   SCL → pino 21   VCC → 5V   GND → GND
//
// Biblioteca necessária (Arduino IDE → Library Manager):
//   "LiquidCrystal I2C", de Frank de Brabander
//
// Protocolo v0: texto, 115200 baud, uma mensagem por linha terminada em '\n'.
// A especificação completa está em docs/protocolo.md.
//   Painel → ponte:  READY | BTN STAGE 1 | BTN STAGE 0 | ERR <linha>
//   Ponte → painel:  SAS 0 | SAS 1 | ALT <metros>
//
// Teste sem o KSP, pelo Serial Monitor (115200 baud, final de linha em
// "Nova linha"): digite "SAS 1", "ALT 12345", "ALT -5"... e veja o LED e o
// LCD. Sem mensagens por 1 segundo, o LCD mostra "sem sinal" e o LED apaga.
//
// Lembre do princípio do projeto: o painel NÃO SABE QUE O KSP EXISTE. Ele
// lê um botão, acende um LED e mostra um número. Quem dá sentido a isso é a
// ponte (bridge/ponte.py).
//
// O que há de novo em relação ao passo 3:
//   - o LCD, desenhado sem piscar e sem travar o laço;
//   - o "sinal": o painel percebe quando a ponte parou de falar com ele e,
//     nesse caso, não fica mostrando dado velho como se fosse atual.

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ================================================================ config =====

const uint8_t PINO_BOTAO_STAGE = 2;
const uint8_t PINO_LED_SAS = 8;

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

// Estado "não sei" do SAS: antes da primeira mensagem ou sem sinal.
const int8_t SAS_DESCONHECIDO = -1;

// ================================================================ estado =====
//
// Tudo que o painel sabe sobre o mundo fica nestas variáveis. As funções de
// entrada (botão, serial) só ALTERAM o estado; as funções de saída (LED, LCD)
// só MOSTRAM o estado. Separar as duas coisas deixa o código fácil de seguir.

// Dados vindos da ponte.
int8_t sas = SAS_DESCONHECIDO;   // -1 = desconhecido, 0 = desligado, 1 = ligado
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

// Debounce do botão (igual ao passo 2).
bool estadoEstavel;
bool ultimaLeitura;
unsigned long instanteMudanca;

// Linha da serial sendo montada (igual ao passo 3).
const uint8_t TAMANHO_LINHA = 32;
char linha[TAMANHO_LINHA];
uint8_t tamanhoLinha = 0;
bool linhaGrandeDemais = false;

// O objeto que conversa com o LCD pelo I2C.
LiquidCrystal_I2C lcd(LCD_ENDERECO, LCD_COLUNAS, LCD_LINHAS);

// ================================================================= botão =====

void lerBotao() {
  bool leitura = digitalRead(PINO_BOTAO_STAGE);
  if (leitura != ultimaLeitura) {
    ultimaLeitura = leitura;
    instanteMudanca = millis();
  }
  if (leitura != estadoEstavel && millis() - instanteMudanca >= DEBOUNCE_MS) {
    estadoEstavel = leitura;
    // Pull-up: apertado = LOW. O painel só avisa; quem decide o que fazer é a ponte.
    if (estadoEstavel == LOW) {
      Serial.println(F("BTN STAGE 1"));
    } else {
      Serial.println(F("BTN STAGE 0"));
    }
  }
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

void processarLinha(const char *texto) {
  long valor;

  if (strncmp(texto, "SAS ", 4) == 0 && lerInteiro(texto + 4, &valor) &&
      (valor == 0 || valor == 1)) {
    registrarMensagem();
    if (valor != sas) {
      sas = valor;
      // O LED é atualizado na hora: é só um pino, custa quase nada.
      digitalWrite(PINO_LED_SAS, sas == 1 ? HIGH : LOW);
      redesenharSas = true;   // o LCD fica para depois (é lento)
    }
    return;
  }

  if (strncmp(texto, "ALT ", 4) == 0 && lerInteiro(texto + 4, &valor)) {
    registrarMensagem();
    // Só marca para redesenhar se o número mudou de verdade.
    if (!altitudeConhecida || valor != altitude) {
      altitude = valor;
      altitudeConhecida = true;
      redesenharAltitude = true;
    }
    return;
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
// velho. Em vez de mostrar um SAS e uma altitude que talvez nem existam
// mais, o painel "esquece" os dados e mostra que está sem sinal.
void verificarSinal() {
  if (comSinal && millis() - ultimaMensagem >= TIMEOUT_SINAL_MS) {
    comSinal = false;
    sas = SAS_DESCONHECIDO;
    altitudeConhecida = false;
    digitalWrite(PINO_LED_SAS, LOW);
    redesenharSinal = true;
    redesenharSas = true;
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
  if (sas == 1) {
    escreverLinha(2, "SAS: ligado");
  } else if (sas == 0) {
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
// 1 ms, e uma linha inteira leva uns 20 ms. Nesse tempo o laço não lê o botão
// nem a serial. Redesenhando só o que mudou, e no máximo 5 vezes por segundo,
// o LCD ocupa uma fração pequena do tempo e o resto fica livre. Mais que isso
// o olho nem acompanha.
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

  pinMode(PINO_BOTAO_STAGE, INPUT_PULLUP);
  estadoEstavel = digitalRead(PINO_BOTAO_STAGE);
  ultimaLeitura = estadoEstavel;
  instanteMudanca = millis();

  pinMode(PINO_LED_SAS, OUTPUT);
  digitalWrite(PINO_LED_SAS, LOW);

  lcd.init();        // inicializa o controlador do LCD (e o I2C)
  lcd.backlight();   // liga a luz de fundo
  escreverLinha(0, "KSP Cockpit");   // linha 0 é fixa, desenhada uma vez só
  // As linhas 1 a 3 já estão marcadas para desenhar ("--" e "sem sinal").

  Serial.println(F("READY"));
}

// O laço inteiro: cada função faz um pedacinho e devolve o controle na hora.
// Nenhuma espera por nada.
void loop() {
  lerBotao();         // entrada: botão → mensagem para a ponte
  lerSerial();        // entrada: mensagens da ponte → estado
  verificarSinal();   // a ponte ainda está falando?
  atualizarLcd();     // saída: estado → LCD
}
