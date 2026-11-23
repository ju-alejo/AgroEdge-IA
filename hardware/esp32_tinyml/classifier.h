#pragma once

#include <stdint.h>

namespace agroedge {

constexpr unsigned windowSize = 6;
constexpr uint32_t intervalMs = 5000;
constexpr uint32_t maxGapMs = 8000;

struct Sample {
  int16_t temperatureCentiC;
  uint16_t humidityCentiPct;
  uint32_t pressureCentiHpa;
};

struct Features {
  int8_t temperature;
  int8_t humidity;
  int8_t pressureChange;
};

inline int8_t quantize(int32_t numerator, int32_t denominator) {
  int32_t value = (numerator >= 0 ? numerator + denominator / 2 : numerator - denominator / 2) / denominator;
  if (value < -128) return -128;
  if (value > 127) return 127;
  return static_cast<int8_t>(value);
}

class SampleWindow {
 public:
  void clear() { count_ = next_ = 0; temperature_ = humidity_ = 0; }

  bool push(Sample sample, uint32_t time, Features &features) {
    if (count_ && time - lastTime_ > maxGapMs) clear();
    lastTime_ = time;
    if (count_ == windowSize) {
      temperature_ -= samples_[next_].temperatureCentiC;
      humidity_ -= samples_[next_].humidityCentiPct;
    } else {
      ++count_;
    }
    temperature_ += sample.temperatureCentiC;
    humidity_ += sample.humidityCentiPct;
    samples_[next_] = sample;
    next_ = (next_ + 1) % windowSize;
    if (count_ < windowSize) return false;
    features = {quantize(temperature_ - windowSizeCenti * 20, windowSizeCenti),
                quantize(humidity_ - windowSizeCenti * 50, windowSizeCenti),
                quantize(static_cast<int32_t>(sample.pressureCentiHpa) -
                             static_cast<int32_t>(samples_[next_].pressureCentiHpa), 5)};
    return true;
  }

 private:
  static constexpr int32_t windowSizeCenti = 100 * windowSize;
  Sample samples_[windowSize]{};
  unsigned count_ = 0;
  unsigned next_ = 0;
  uint32_t lastTime_ = 0;
  int32_t temperature_ = 0;
  int32_t humidity_ = 0;
};

struct Classification {
  unsigned index;
  int32_t distance;
  int32_t runnerUp;

  double score() const { return static_cast<double>(runnerUp - distance) / (runnerUp + distance + 1); }
};

template <unsigned N>
Classification classify(Features features, const Features (&centroids)[N]) {
  static_assert(N >= 2, "At least two classes are required");
  Classification result{0, INT32_MAX, INT32_MAX};
  for (unsigned i = 0; i < N; ++i) {
    const int32_t t = features.temperature - centroids[i].temperature;
    const int32_t h = features.humidity - centroids[i].humidity;
    const int32_t p = features.pressureChange - centroids[i].pressureChange;
    const int32_t distance = t * t + h * h + p * p;
    if (distance < result.distance) {
      result = {i, distance, result.distance};
    } else if (distance < result.runnerUp) {
      result.runnerUp = distance;
    }
  }
  return result;
}

}  // namespace agroedge
