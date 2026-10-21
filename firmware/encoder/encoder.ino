const char NOME[] = "AJUSTE";

const uint8_t PINO_A = 2;
const uint8_t PINO_B = 3;
const uint8_t PINO_BOTAO = 4;

const unsigned long DEBOUNCE_MS = 20;

const int8_t PASSO[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

volatile int16_t cliques = 0;
uint8_t ultimoAB;
int8_t quartos = 0;

bool botaoEstavel;
bool botaoUltimaLeitura;
unsigned long botaoInstanteMudanca;

uint8_t lerAB() {
  return (digitalRead(PINO_A) << 1) | digitalRead(PINO_B);
}

void girou() {
  uint8_t ab = lerAB();
  quartos += PASSO[(ultimoAB << 2) | ab];
  ultimoAB = ab;
  if (ab == 0b11) {
    if (quartos >= 2) {
      cliques++;
    } else if (quartos <= -2) {
      cliques--;
    }
    quartos = 0;
  }
}

void enviarCliques() {
  noInterrupts();
  int16_t n = cliques;
  cliques = 0;
  interrupts();
  if (n != 0) {
    Serial.print(F("ENC "));
    Serial.print(NOME);
    Serial.print(' ');
    Serial.println(n);
  }
}

void lerBotao() {
  bool leitura = digitalRead(PINO_BOTAO);
  if (leitura != botaoUltimaLeitura) {
    botaoUltimaLeitura = leitura;
    botaoInstanteMudanca = millis();
  }
  if (leitura != botaoEstavel && millis() - botaoInstanteMudanca >= DEBOUNCE_MS) {
    botaoEstavel = leitura;
    Serial.print(F("BTN "));
    Serial.print(NOME);
    Serial.println(leitura == LOW ? F(" 1") : F(" 0"));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_A, INPUT_PULLUP);
  pinMode(PINO_B, INPUT_PULLUP);
  pinMode(PINO_BOTAO, INPUT_PULLUP);
  ultimoAB = lerAB();
  botaoEstavel = digitalRead(PINO_BOTAO);
  botaoUltimaLeitura = botaoEstavel;
  botaoInstanteMudanca = millis();
  attachInterrupt(digitalPinToInterrupt(PINO_A), girou, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PINO_B), girou, CHANGE);
  Serial.println(F("READY"));
}

void loop() {
  enviarCliques();
  lerBotao();
}
