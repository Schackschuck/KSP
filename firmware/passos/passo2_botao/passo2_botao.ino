// Fase 1 — Passo 2: botão com debounce, avisando pela serial
//
// Montagem:
//   pino 2 ──[botão]── GND      (sem resistor: usa o pull-up interno do Mega)
//
// Teste: abra o Serial Monitor em 115200 baud. Cada aperto deve imprimir
// exatamente uma linha "BTN STAGE 1" (apertou) e uma "BTN STAGE 0" (soltou),
// mesmo apertando rápido várias vezes.
//
// -----------------------------------------------------------------------------
// Conceito 1: pull-up
// -----------------------------------------------------------------------------
// Um pino de entrada ligado a nada fica "flutuando": lê HIGH ou LOW ao acaso,
// conforme o ruído elétrico em volta. O pull-up é um resistor (uns 20 a 50 kΩ,
// dentro do próprio chip) que puxa o pino para 5 V quando nada mais o puxa.
// Com o botão ligado entre o pino e o GND:
//
//   botão solto    → o resistor puxa o pino para 5 V → lê HIGH
//   botão apertado → o botão liga o pino direto no GND → lê LOW
//
// A lógica fica invertida: APERTADO = LOW. Parece estranho, mas é o jeito
// mais comum de ligar botões, porque dispensa resistor externo.
//
// -----------------------------------------------------------------------------
// Conceito 2: bounce (trepidação do contato)
// -----------------------------------------------------------------------------
// Por dentro, o botão tem duas lâminas de metal. Quando elas se encostam,
// quicam por alguns milissegundos antes de firmar, e o pino vê
// HIGH, LOW, HIGH, LOW... O Mega lê o pino dezenas de milhares de vezes por
// segundo, então enxerga cada quique como um aperto novo. Um aperto viraria
// vários "BTN STAGE 1", e cada um separaria um estágio do foguete!
//
// Debounce = só aceitar uma mudança depois que a leitura ficar ESTÁVEL por um
// tempo mínimo (aqui, 20 ms). Enquanto o contato quica, a leitura muda o tempo
// todo e o cronômetro é zerado a cada mudança. Quando ele firma, a leitura
// para de mudar, os 20 ms passam e a mudança é aceita, uma vez só.
//
// Para ver o bounce acontecer, mude DEBOUNCE_MS para 0 e aperte o botão
// algumas vezes.

const uint8_t PINO_BOTAO_STAGE = 2;
const unsigned long DEBOUNCE_MS = 20;

// Estado do debounce.
bool estadoEstavel;              // último estado aceito (HIGH = solto, LOW = apertado)
bool ultimaLeitura;              // última leitura crua do pino, ainda com quiques
unsigned long instanteMudanca;   // quando a leitura crua mudou pela última vez

void lerBotao() {
  bool leitura = digitalRead(PINO_BOTAO_STAGE);

  // A leitura crua mudou: pode ser quique. Zera o cronômetro.
  if (leitura != ultimaLeitura) {
    ultimaLeitura = leitura;
    instanteMudanca = millis();
  }

  // A leitura é diferente do estado aceito E está parada há DEBOUNCE_MS:
  // a mudança é de verdade. Aceita e avisa pela serial.
  if (leitura != estadoEstavel && millis() - instanteMudanca >= DEBOUNCE_MS) {
    estadoEstavel = leitura;

    // F("...") guarda o texto na memória flash (onde fica o programa) em vez
    // da RAM. O Mega tem 256 KB de flash e só 8 KB de RAM, então textos fixos
    // devem ir para a flash. É um hábito que vale criar desde já.
    if (estadoEstavel == LOW) {
      Serial.println(F("BTN STAGE 1"));   // LOW = apertado (pull-up!)
    } else {
      Serial.println(F("BTN STAGE 0"));
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_BOTAO_STAGE, INPUT_PULLUP);   // entrada com o pull-up interno ligado

  // Começa com o estado real do botão. Assim, se ele já estiver apertado
  // quando a placa ligar, isso não vira um aperto falso.
  estadoEstavel = digitalRead(PINO_BOTAO_STAGE);
  ultimaLeitura = estadoEstavel;
  instanteMudanca = millis();
}

void loop() {
  lerBotao();
  // Nada de delay(): o laço fica livre para as próximas tarefas.
}
