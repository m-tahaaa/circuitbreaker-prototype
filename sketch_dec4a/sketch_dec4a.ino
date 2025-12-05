const int CT_PIN = A0;
const float VREF = 5.0;
const float ADC_RES = 1023.0;
const int NUM_SAMPLES = 2000;
const float CURRENT_PER_VOLT = 30.0;
unsigned long lastRead = 0;

void setup() {
  Serial.begin(115200);
  DDRD = 0xFF; // Set Port D as output for Stepper
}

void loop() {
  // 1. Listen for Commands from Python Bridge
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "TRIP") motorTrip();
    if (cmd == "RESET") motorReset();
  }

  // 2. Send Data every 1 second
  if (millis() - lastRead > 1000) {
    readAndSendCurrent();
    lastRead = millis();
  }
}

void readAndSendCurrent() {
  double sumSquares = 0;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    int raw = analogRead(CT_PIN);
    float voltage = (raw * VREF) / ADC_RES;
    float centered = voltage - (VREF / 2.0);
    sumSquares += centered * centered;
  }
  float Vrms = sqrt(sumSquares / NUM_SAMPLES);
  float Irms = Vrms * CURRENT_PER_VOLT;

  // FORMAT: SubstationID, LineID, Voltage(fake), Current
  Serial.print("SUB_1,LINE_A,230.0,"); 
  Serial.println(Irms, 3);
}

// --- Your Existing Motor Logic ---
void motorTrip() {
  int k = 0;
  while (k < 25) {
    for (int i = 0x10; i <= 0x80; i <<= 1) {
      PORTD = i; delay(10);
    }
    k++;
  }
  PORTD = 0x00;
}

void motorReset() {
  int k = 0;
  while (k < 25) {
    for (int i = 0x80; i >= 0x10; i >>= 1) {   
      PORTD = i; delay(10);
    }
    k++;
  }
  PORTD = 0x00;
}