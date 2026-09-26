// Fase 1 — Passo 3: receber comandos pela serial (SAS 1 / SAS 0 → LED)
//
// Montagem: o botão do passo 2 e o LED do passo 1, juntos.
//   pino 2 ──[botão]── GND
//   pino 8 ──[220 Ω]──(+)LED(−)── GND
//
// Teste, no Serial Monitor em 115200 baud, com o final de linha em
// "Nova linha" (ou "Ambos, NL e CR"):
//   - ao abrir, aparece "READY";
//   - digitar "SAS 1" acende o LED e "SAS 0" apaga;
//   - digitar qualquer outra coisa responde "ERR <o que foi digitado>";
//   - o botão continua respondendo na hora, como no passo 2.
//
// -----------------------------------------------------------------------------
// O que este passo ensina
// -----------------------------------------------------------------------------
// A serial não entrega "mensagens", entrega BYTES, um de cada vez, conforme
// chegam. "SAS 1\n" chega como 'S', 'A', 'S', ' ', '1', '\n', possivelmente
// em voltas diferentes do loop(). Por isso o protocolo tem uma regra:
// toda mensagem termina com '\n' (quebra de linha).
//
// O firmware guarda os caracteres num buffer (um vetor de char) até chegar o
// '\n'. Só então a linha está completa e pode ser interpretada.
//
// Por que não usar Serial.readString() ou Serial.readStringUntil('\n')?
// Porque elas ESPERAM (até 1 segundo, por padrão) por mais dados. Seria um
// delay() disfarçado, e o botão pararia de responder.
//
// E por que não usar a classe String? Ela aloca memória dinamicamente, e com
// só 8 KB de RAM a memória vai ficando "picotada" até faltar. Em firmware que
// fica ligado horas, o normal é usar vetores de tamanho fixo.

// ---------------------------------------------------------------- pinos -----
const uint8_t PINO_BOTAO_STAGE = 2;
const uint8_t PINO_LED_SAS = 8;

// --------------------------------------------------------- botão (passo 2) --
const unsigned long DEBOUNCE_MS = 20;
bool estadoEstavel;
bool ultimaLeitura;
unsigned long instanteMudanca;

void lerBotao() {
  bool leitura = digitalRead(PINO_BOTAO_STAGE);
  if (leitura != ultimaLeitura) {
    ultimaLeitura = leitura;
    instanteMudanca = millis();
  }
  if (leitura != estadoEstavel && millis() - instanteMudanca >= DEBOUNCE_MS) {
    estadoEstavel = leitura;
    if (estadoEstavel == LOW) {
      Serial.println(F("BTN STAGE 1"));
    } else {
      Serial.println(F("BTN STAGE 0"));
    }
  }
}

// ------------------------------------------------------ comandos (novo) -----

// Tamanho máximo de uma linha, contando o '\0' que termina toda string em C.
// "SAS 1" tem 5 caracteres; 32 dá folga de sobra.
const uint8_t TAMANHO_LINHA = 32;

char linha[TAMANHO_LINHA];      // os caracteres da linha que está chegando
uint8_t tamanhoLinha = 0;       // quantos caracteres já chegaram
bool linhaGrandeDemais = false; // passou do tamanho? então descarta a linha inteira

// Tenta ler um número inteiro de 'texto'. Devolve true se o texto inteiro
// era um número (ex.: "1", "-42") e guarda o valor em 'valor'.
bool lerInteiro(const char *texto, long *valor) {
  char *fim;
  // strtol converte texto em número e aponta 'fim' para onde a conversão parou.
  *valor = strtol(texto, &fim, 10);
  // Deu certo se converteu pelo menos um dígito (fim andou) e se não sobrou
  // nada depois do número (fim chegou no '\0'). Assim "1x" e "" são recusados.
  return fim != texto && *fim == '\0';
}

// Interpreta uma linha completa, já sem o '\n'.
void processarLinha(const char *texto) {
  long valor;

  // strncmp compara só os 4 primeiros caracteres: a linha começa com "SAS "?
  // Se sim, o número começa logo depois deles, em texto + 4.
  if (strncmp(texto, "SAS ", 4) == 0 && lerInteiro(texto + 4, &valor) &&
      (valor == 0 || valor == 1)) {
    digitalWrite(PINO_LED_SAS, valor == 1 ? HIGH : LOW);
    return;
  }

  // Não reconheceu: avisa quem mandou. Ajuda muito a depurar.
  Serial.print(F("ERR "));
  Serial.println(texto);
}

// Lê os bytes que chegaram e monta as linhas. Nunca espera: se não chegou
// nada, volta na hora.
void lerSerial() {
  // Serial.available() diz quantos bytes estão esperando no buffer de
  // recepção (o hardware guarda até 64 enquanto o loop() faz outras coisas).
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\r') {
      continue;  // o Windows às vezes manda "\r\n"; o '\r' é ignorado
    }

    if (c == '\n') {
      // Fim da linha. Coloca o '\0' que marca o fim da string em C...
      linha[tamanhoLinha] = '\0';
      // ...e processa, a não ser que esteja vazia ou tenha estourado.
      if (tamanhoLinha > 0 && !linhaGrandeDemais) {
        processarLinha(linha);
      }
      // Prepara para a próxima linha.
      tamanhoLinha = 0;
      linhaGrandeDemais = false;
    } else if (tamanhoLinha < TAMANHO_LINHA - 1) {
      linha[tamanhoLinha] = c;   // guarda o caractere (o "- 1" reserva o '\0')
      tamanhoLinha++;
    } else {
      // Não cabe. Nunca escreva fora do vetor: em C nada impede, e o
      // resultado é corromper outras variáveis. Marca e descarta a linha.
      linhaGrandeDemais = true;
    }
  }
}

// --------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);

  pinMode(PINO_BOTAO_STAGE, INPUT_PULLUP);
  estadoEstavel = digitalRead(PINO_BOTAO_STAGE);
  ultimaLeitura = estadoEstavel;
  instanteMudanca = millis();

  pinMode(PINO_LED_SAS, OUTPUT);
  digitalWrite(PINO_LED_SAS, LOW);

  // Avisa que terminou de ligar. A ponte (passo 5) espera essa linha antes de
  // mandar qualquer coisa, porque o que chegar antes disso se perde.
  Serial.println(F("READY"));
}

void loop() {
  lerBotao();
  lerSerial();
}
