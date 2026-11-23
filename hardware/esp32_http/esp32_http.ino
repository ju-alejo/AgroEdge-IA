// Configure these values with your own local network information.
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <time.h>
#include <esp_system.h>

const char* ssid = "NOMBRE_DE_TU_RED";
const char* password = "CLAVE_DE_TU_RED";
const char* endpoint = "http://IP_REAL_DEL_PC:5173/api/measurements/wifi";
const char* token = "TOKEN_CONFIGURADO_EN_AGROEDGE";
const char* station = "TOCA-WIFI-01";
Adafruit_BME280 bme;
bool sensorReady = false;
uint32_t sequence = 0;
char sessionId[32];
String pending;

String numberOrNull(float value) {
  return isfinite(value) ? String(value, 2) : String("null");
}
void setup() {
  Serial.begin(115200);
  Wire.begin();
  sensorReady = bme.begin(0x76) || bme.begin(0x77);
  snprintf(sessionId, sizeof(sessionId), "boot-%08lx%08lx",
           (unsigned long)esp_random(), (unsigned long)esp_random());
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid, password);
  configTime(0, 0, "pool.ntp.org", "time.google.com");
}
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    delay(2000);
    return;
  }
  if (pending.isEmpty()) {
    struct tm utc;
    if (!getLocalTime(&utc, 2000) || utc.tm_year < 124) {
      Serial.println("Esperando sincronizacion NTP.");
      return;
    }
    char timestamp[25];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utc);
    // Add classification only when the device actually runs the TinyML model.
    pending = String("{\"schemaVersion\":1,\"origin\":\"WIFI\",\"stationId\":\"") + station
      + "\",\"sessionId\":\"" + sessionId + "\",\"sequence\":" + String(++sequence)
      + ",\"acquiredAt\":\"" + timestamp + "\",\"temperature\":" + numberOrNull(sensorReady ? bme.readTemperature() : NAN)
      + ",\"humidity\":" + numberOrNull(sensorReady ? bme.readHumidity() : NAN)
      + ",\"pressure\":" + numberOrNull(sensorReady ? bme.readPressure() / 100.0F : NAN) + "}";
  }
  WiFiClient socket;
  HTTPClient http;
  if (http.begin(socket, endpoint)) {
    http.setTimeout(5000);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", String("Bearer ") + token);
    const int status = http.POST(pending);
    Serial.printf("AgroEdge HTTP %d\n", status);
    if (status == 200 || status == 201) pending = "";
    http.end();
  }
  delay(2000);
}

