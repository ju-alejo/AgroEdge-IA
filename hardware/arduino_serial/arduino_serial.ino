// BME280 over I2C. Open the actual COM port from AgroEdge, at 115200.
#include <Wire.h>
#include <EEPROM.h>
#include <Adafruit_BME280.h>

Adafruit_BME280 bme;
const char* station = "TOCA-USB-01";
uint32_t bootNumber = 0;
uint32_t sequence = 0;
bool sensorReady = false;

void printNumber(float value) {
  if (isfinite(value)) Serial.print(value, 2);
  else Serial.print(F("null"));
}
void setup() {
  Serial.begin(115200);
  Wire.begin();
  sensorReady = bme.begin(0x76) || bme.begin(0x77);
  EEPROM.get(0, bootNumber);
  if (bootNumber == UINT32_MAX) bootNumber = 0;
  bootNumber++;
  EEPROM.put(0, bootNumber);
}
void loop() {
  Serial.print(F("{\"schemaVersion\":1,\"origin\":\"USB\",\"stationId\":\""));
  Serial.print(station);
  Serial.print(F("\",\"sessionId\":\"boot-"));
  Serial.print(bootNumber);
  Serial.print(F("\",\"sequence\":"));
  Serial.print(++sequence);
  Serial.print(F(",\"temperature\":"));
  printNumber(sensorReady ? bme.readTemperature() : NAN);
  Serial.print(F(",\"humidity\":"));
  printNumber(sensorReady ? bme.readHumidity() : NAN);
  Serial.print(F(",\"pressure\":"));
  printNumber(sensorReady ? bme.readPressure() / 100.0F : NAN);
  Serial.println(F("}"));
  delay(2000);
}

