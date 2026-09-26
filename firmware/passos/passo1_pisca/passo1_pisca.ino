// Fase 1 — Passo 1: piscar um LED sem usar delay()
//
// Montagem:
//   pino 8 ──[220 Ω]──(+)LED(−)── GND      (perna longa do LED = +)
//
// Teste: o LED pisca uma vez por segundo. Abra o Serial Monitor em 115200
// baud: a cada segundo aparece quantas voltas o loop() deu nesse tempo.
//
// -----------------------------------------------------------------------------
// O que este passo ensina
// -----------------------------------------------------------------------------
// O jeito "de tutorial" de piscar um LED é:
//
//     digitalWrite(LED, HIGH); delay(500);
//     digitalWrite(LED, LOW);  delay(500);
//
// Funciona, mas durante cada delay() o microcontrolador fica PARADO: não lê
// botão, não lê a serial, não faz mais nada. No painel isso seria um desastre:
// um aperto de botão durante o delay() simplesmente se perderia.
//
// A alternativa é o laço sem bloqueio. O loop() roda dezenas de milhares de
// vezes por segundo e, a cada volta, pergunta: "já passou tempo suficiente
// desde a última vez que troquei o LED?". Se passou, troca. Se não passou,
// segue em frente e deixa o laço livre para as outras tarefas.
//
// millis() devolve quantos milissegundos se passaram desde que a placa ligou.
// Este sketch tem DUAS tarefas com tempos diferentes (piscar o LED e imprimir
// a contagem), e uma não atrapalha a outra. É exatamente assim que o painel
// vai ler botão, ler a serial e atualizar o LCD "ao mesmo tempo".

// Constantes com nome em vez de "números mágicos" espalhados pelo código.
// "const" faz o compilador impedir que alguém mude o valor sem querer.
// uint8_t = inteiro sem sinal de 8 bits (0 a 255): o suficiente para um pino.
const uint8_t PINO_LED = 8;
const unsigned long INTERVALO_PISCA_MS = 500;      // 500 ms aceso + 500 ms apagado = 1 Hz
const unsigned long INTERVALO_CONTAGEM_MS = 1000;

// Variáveis globais guardam o estado entre uma volta do loop() e a próxima.
// (Uma variável declarada dentro do loop() nasceria de novo a cada volta.)
unsigned long ultimaTrocaLed = 0;    // instante, em ms, da última troca do LED
bool ledAceso = false;

unsigned long ultimaContagem = 0;
unsigned long voltas = 0;            // quantas vezes o loop() rodou no último segundo

void setup() {
  // setup() roda uma vez só, quando a placa liga ou reinicia.
  pinMode(PINO_LED, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  unsigned long agora = millis();
  voltas++;

  // Tarefa 1: piscar o LED.
  //
  // Por que "agora - ultimaTrocaLed >= INTERVALO" e não
  // "agora >= ultimaTrocaLed + INTERVALO"? O millis() é um número de 32 bits
  // e, depois de uns 49,7 dias ligado, ele "dá a volta" e recomeça do zero.
  // Na subtração entre números sem sinal, o resultado continua certo mesmo
  // nessa virada. Com a soma, o LED travaria no dia 50.
  if (agora - ultimaTrocaLed >= INTERVALO_PISCA_MS) {
    ultimaTrocaLed = agora;
    ledAceso = !ledAceso;
    digitalWrite(PINO_LED, ledAceso ? HIGH : LOW);
  }

  // Tarefa 2: mostrar quantas voltas o loop() deu no último segundo.
  // O número deve ficar na casa das dezenas de milhares, ou mais. Experimente
  // colocar um delay(500) no fim do loop() e veja o que acontece com ele.
  if (agora - ultimaContagem >= INTERVALO_CONTAGEM_MS) {
    ultimaContagem = agora;
    Serial.print("Voltas do loop() no ultimo segundo: ");
    Serial.println(voltas);
    voltas = 0;
  }
}
