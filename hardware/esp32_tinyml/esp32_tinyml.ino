#include <Adafruit_BMP280.h>
#include <Wire.h>
#include <esp_random.h>
#include <esp_timer.h>
#include <math.h>

#include "model.h"
#include "benchmark.h"

constexpr char stationId[] = "TOCA-ESP32-01";
constexpr uint8_t ahtAddress = 0x38;
constexpr uint8_t bmpAddress = 0x77;
Adafruit_BMP280 bmp(&Wire);
agroedge::SampleWindow window;
char sessionId[35];
uint32_t sequence = 0;
uint32_t lastSample = 0;
bool bmpReady = false;

static void handleDiagnostics() {
  static char command[24];
  static unsigned length = 0;
  static bool overflow = false;
  while (Serial.available()) {
    const int c = Serial.read();
    if (c != '\n') {
      if (length < sizeof(command) - 1) command[length++] = static_cast<char>(c);
      else overflow = true;
      continue;
    }
    command[length] = '\0';
    if (!overflow && strcmp(command, "B") == 0) agroedge::reportBenchmark(Serial);
    int t, h, p;
    char extra;
    if (!overflow && sscanf(command, "Q %4d %4d %4d %c", &t, &h, &p, &extra) == 3 &&
        t >= -128 && t <= 127 && h >= -128 && h <= 127 && p >= -128 && p <= 127) {
      const agroedge::Features input{static_cast<int8_t>(t), static_cast<int8_t>(h), static_cast<int8_t>(p)};
      const auto result = agroedge::classify(input, agroedge::centroids);
      Serial.printf("{\"event\":\"prediction\",\"modelVersion\":\"%s\",\"features\":[%d,%d,%d],\"index\":%u}\n",
                    agroedge::modelVersion, t, h, p, result.index);
    }
    length = 0;
    overflow = false;
  }
}

static bool inRange(float value, float minimum, float maximum) {
  return isfinite(value) && value >= minimum && value <= maximum;
}

static bool responds(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

static bool ahtCommand(uint8_t command, uint8_t parameter) {
  Wire.beginTransmission(ahtAddress);
  Wire.write(command);
  Wire.write(parameter);
  Wire.write(0);
  return Wire.endTransmission() == 0;
}

static bool readAht20(float &temperature, float &humidity) {
  constexpr uint8_t busy = 0x80;
  constexpr uint8_t calibrated = 0x08;
  if (Wire.requestFrom(ahtAddress, 1) != 1) return false;
  const uint8_t status = Wire.read();
  if (status & busy) return false;
  if (!(status & calibrated)) {
    if (!ahtCommand(0xBE, 0x08)) return false;
    delay(20);
  }
  if (!ahtCommand(0xAC, 0x33)) return false;
  delay(80);
  uint8_t data[7];
  for (unsigned attempt = 0; attempt < 4; ++attempt) {
    if (Wire.requestFrom(ahtAddress, sizeof(data)) != sizeof(data)) return false;
    for (auto &value : data) value = Wire.read();
    if (!(data[0] & busy)) break;
    delay(10);
  }
  if ((data[0] & (busy | calibrated)) != calibrated) return false;

  uint8_t crc = 0xFF;
  for (unsigned i = 0; i < 6; ++i) {
    crc ^= data[i];
    for (unsigned bit = 0; bit < 8; ++bit) crc = (crc & 0x80) ? (crc << 1) ^ 0x31 : crc << 1;
  }
  if (crc != data[6]) return false;
  const uint32_t rawHumidity = (uint32_t(data[1]) << 12) | (uint32_t(data[2]) << 4) | (data[3] >> 4);
  const uint32_t rawTemperature = (uint32_t(data[3] & 0x0F) << 16) | (uint32_t(data[4]) << 8) | data[5];
  humidity = rawHumidity * (100.0f / 1048576.0f);
  temperature = rawTemperature * (200.0f / 1048576.0f) - 50.0f;
  return true;
}

static void writeValue(const char *key, float value) {
  Serial.printf(",\"%s\":", key);
  if (isfinite(value)) Serial.printf("%.2f", value);
  else Serial.print("null");
}

static void acquire() {
  float temperature = NAN, humidity = NAN, pressure = NAN;
  if (!bmpReady && responds(bmpAddress)) {
    bmpReady = bmp.begin(bmpAddress);
    if (bmpReady) {
      bmp.setSampling(Adafruit_BMP280::MODE_NORMAL, Adafruit_BMP280::SAMPLING_X2,
                      Adafruit_BMP280::SAMPLING_X4, Adafruit_BMP280::FILTER_OFF,
                      Adafruit_BMP280::STANDBY_MS_250);
      delay(25);
    }
  }
  readAht20(temperature, humidity);
  if (!inRange(temperature, -40, 85)) temperature = NAN;
  if (!inRange(humidity, 0, 100)) humidity = NAN;
  bmpReady = bmpReady && responds(bmpAddress);
  if (bmpReady) {
    const float hpa = bmp.readPressure() / 100.0f;
    if (inRange(hpa, 300, 1100)) pressure = hpa;
  }

  const bool valid = isfinite(temperature) && isfinite(humidity) && isfinite(pressure);
  bool classified = false;
  auto inference = agroedge::Classification{};
  int64_t inferenceUs = 0;
  if (valid) {
    const agroedge::Sample sample{static_cast<int16_t>(lroundf(temperature * 100)),
                                  static_cast<uint16_t>(lroundf(humidity * 100)),
                                  static_cast<uint32_t>(lroundf(pressure * 100))};
    agroedge::Features features{};
    classified = window.push(sample, lastSample, features);
    if (classified) {
      const int64_t start = esp_timer_get_time();
      inference = agroedge::classify(features, agroedge::centroids);
      inferenceUs = esp_timer_get_time() - start;
    }
    // Serialize the same centesimal values used by the model.
    temperature = sample.temperatureCentiC / 100.0f;
    humidity = sample.humidityCentiPct / 100.0f;
    pressure = sample.pressureCentiHpa / 100.0f;
  } else {
    window.clear();
  }

  Serial.printf("{\"schemaVersion\":1,\"stationId\":\"%s\",\"sessionId\":\"%s\",\"sequence\":%lu",
                stationId, sessionId, static_cast<unsigned long>(++sequence));
  writeValue("temperature", temperature);
  writeValue("humidity", humidity);
  writeValue("pressure", pressure);
  if (classified || !valid) {
    Serial.printf(",\"classification\":{\"source\":\"ESP32\",\"modelVersion\":\"%s\",\"modelStatus\":\"%s\"",
                  agroedge::modelVersion, agroedge::modelStatus);
    if (classified) {
      Serial.printf(",\"state\":\"OK\",\"label\":\"%s\",\"score\":%.6f,\"inferenceUs\":%lld}",
                    agroedge::labelText[inference.index], inference.score(), static_cast<long long>(inferenceUs));
    } else Serial.print(",\"state\":\"ERROR\",\"label\":null,\"score\":null}");
  }
  Serial.println("}");
}

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);
  Wire.setTimeOut(50);
  delay(100);
  snprintf(sessionId, sizeof(sessionId), "s3-%012llx-%08lx-%08lx",
           static_cast<unsigned long long>(ESP.getEfuseMac()), static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(esp_random()));
  lastSample = millis() - agroedge::intervalMs;
}

void loop() {
  handleDiagnostics();
  const uint32_t now = millis();
  if (now - lastSample >= agroedge::intervalMs) {
    lastSample = now;
    acquire();
  }
  delay(10);
}
