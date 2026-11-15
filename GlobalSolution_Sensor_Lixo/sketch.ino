
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// BINOVA - FIAP Global Solution 2026/2
// Monitoramento inteligente de lixeiras

// -1 = usar o sensor HC-SR04 normalmente
//  1 a 100 = informar um percentual manualmente
//
// Exemplos:
// NIVEL_MANUAL = 25; -> 25%
// NIVEL_MANUAL = 53; -> 53%
// NIVEL_MANUAL = 83; -> 83%
// NIVEL_MANUAL = 100; -> 100%

const int NIVEL_MANUAL = -1;

const byte PINO_TRIG = 8;
const byte PINO_ECHO = 2;

const byte LED_VERDE = A0;
const byte LED_AMARELO = A1;
const byte LED_VERMELHO = A2;
const byte PINO_BUZZER = A3;

// CONFIGURACOES DA LIXEIRA

const float DISTANCIA_VAZIA = 25.0;
const float DISTANCIA_CHEIA = 5.0;

const unsigned long INTERVALO = 2000;

LiquidCrystal_I2C lcd(0x27, 16, 2);

unsigned long ultimaLeitura = 0;
int faixaAnterior = -1;

// Mede a distancia do HC-SR04.
float medirDistancia() {
  digitalWrite(PINO_TRIG, LOW);
  delayMicroseconds(2);

  digitalWrite(PINO_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PINO_TRIG, LOW);

  unsigned long duracao = pulseIn(
    PINO_ECHO, HIGH, 30000UL
  );

  if (duracao == 0) {
    return -1;
  }

  float distancia = duracao * 0.0343 / 2.0;

  if (distancia < 2 || distancia > 400) {
    return -1;
  }

  return distancia;
}

// Filtra cinco medidas utilizando a mediana.
float medirComFiltro() {
  float valores[5];
  byte quantidade = 0;

  for (byte i = 0; i < 5; i++) {
    float distancia = medirDistancia();

    if (distancia >= 0) {
      valores[quantidade++] = distancia;
    }

    delay(60);
  }

  if (quantidade < 3) {
    return -1;
  }

  for (byte i = 1; i < quantidade; i++) {
    float atual = valores[i];
    int j = i - 1;

    while (j >= 0 && valores[j] > atual) {
      valores[j + 1] = valores[j];
      j--;
    }

    valores[j + 1] = atual;
  }

  return valores[quantidade / 2];
}

// Converte a distancia em percentual.
int calcularPercentual(float distancia) {
  float percentual = 100.0 *
    (DISTANCIA_VAZIA - distancia) /
    (DISTANCIA_VAZIA - DISTANCIA_CHEIA);

  percentual = constrain(percentual, 0.0, 100.0);

  return (int)(percentual + 0.5);
}

// Identifica a faixa de preenchimento.
int identificarFaixa(int nivel) {
  if (nivel < 50) return 0;
  if (nivel < 75) return 1;
  if (nivel < 95) return 2;

  return 3;
}

// Exibe a situacao da lixeira no LCD.
void atualizarLCD(int nivel, bool valido) {
  lcd.clear();

  if (!valido) {
    lcd.setCursor(0, 0);
    lcd.print("BINOVA SEM DADOS");

    lcd.setCursor(0, 1);
    lcd.print("VERIFIQUE SENSOR");
    return;
  }

  lcd.setCursor(0, 0);
  lcd.print("BINOVA: ");
  lcd.print(nivel);
  lcd.print("%");

  lcd.setCursor(0, 1);

  if (nivel < 50) {
    lcd.print("DISPONIVEL");
  }
  else if (nivel < 75) {
    lcd.print("ATENCAO");
  }
  else if (nivel < 95) {
    lcd.print("PROX. DO LIMITE");
  }
  else {
    lcd.print("CHEIO");
  }
}

// Controla os LEDs e os alertas sonoros.
void atualizarIndicadores(int nivel, bool valido) {
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_AMARELO, LOW);
  digitalWrite(LED_VERMELHO, LOW);

  if (!valido) {
    noTone(PINO_BUZZER);
    faixaAnterior = -1;
    return;
  }

  int faixa = identificarFaixa(nivel);

  if (faixa == 0) {
    digitalWrite(LED_VERDE, HIGH);
  }
  else if (faixa == 1) {
    digitalWrite(LED_AMARELO, HIGH);
  }
  else {
    digitalWrite(LED_VERMELHO, HIGH);
  }

  // O buzzer toca ao entrar em uma faixa critica.
  if (faixa != faixaAnterior) {
    if (faixa == 2) {
      tone(PINO_BUZZER, 1100, 500);
    }
    else if (faixa == 3) {
      tone(PINO_BUZZER, 1500, 1000);
    }
  }

  faixaAnterior = faixa;
}

// Identifica se o percentual veio do sensor ou manualmente.
void enviarSerial(
  float distancia,
  int nivel,
  bool valido,
  bool manual
) {
  if (!valido) {
    Serial.print("{\"valida\":false,\"modo\":\"");
    Serial.print(manual ? "manual" : "sensor");
    Serial.println("\"}");
    return;
  }

  Serial.print("{");

  if (!manual) {
    Serial.print("\"distanciaCm\":");
    Serial.print(distancia, 1);
    Serial.print(",");
  }

  Serial.print("\"nivelPercentual\":");
  Serial.print(nivel);

  Serial.print(",\"valida\":true,\"modo\":\"");
  Serial.print(manual ? "manual" : "sensor");
  Serial.println("\"}");
}

// Executa o monitoramento da lixeira.
void monitorarLixeira() {

  // Utiliza exatamente o percentual escolhido.
  if (NIVEL_MANUAL != -1) {

    if (NIVEL_MANUAL < 1 || NIVEL_MANUAL > 100) {
      atualizarIndicadores(0, false);

      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("VALOR INVALIDO");
      lcd.setCursor(0, 1);
      lcd.print("USE DE 1 A 100");

      Serial.println(
        "{\"valida\":false,\"modo\":\"manual\","
        "\"erro\":\"valor fora de 1 a 100\"}"
      );
      return;
    }

    atualizarLCD(NIVEL_MANUAL, true);
    atualizarIndicadores(NIVEL_MANUAL, true);

    enviarSerial(-1, NIVEL_MANUAL, true, true);
    return;
  }

  // Calcula o percentual a partir do HC-SR04.
  float distancia = medirComFiltro();

  bool valido =
    distancia >= 0 &&
    DISTANCIA_VAZIA > DISTANCIA_CHEIA;

  int nivel = valido ? calcularPercentual(distancia) : 0;

  atualizarLCD(nivel, valido);
  atualizarIndicadores(nivel, valido);

  enviarSerial(distancia, nivel, valido, false);
}

// Inicializa os componentes.
void setup() {
  pinMode(PINO_TRIG, OUTPUT);
  pinMode(PINO_ECHO, INPUT);

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARELO, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);
  pinMode(PINO_BUZZER, OUTPUT);

  digitalWrite(PINO_TRIG, LOW);

  Serial.begin(9600);

  lcd.init();
  lcd.backlight();

  lcd.setCursor(0, 0);
  lcd.print("BINOVA INICIANDO");

  monitorarLixeira();

  ultimaLeitura = millis();
}

// Atualiza o sistema a cada dois segundos.
void loop() {
  unsigned long agora = millis();

  if (agora - ultimaLeitura >= INTERVALO) {
    ultimaLeitura = agora;

    monitorarLixeira();
  }
}
