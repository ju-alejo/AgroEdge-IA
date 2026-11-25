#pragma once

#include <Arduino.h>
#include <esp_cpu.h>
#include <esp_heap_caps.h>
#include <esp_ota_ops.h>
#include <esp_timer.h>
#include <math.h>

#include "inference.h"

namespace agroedge {

// Keep the measured kernel callable and observable even with link-time optimization.
inline __attribute__((noinline, noipa)) unsigned benchmarkInference(Features features) {
  unsigned index = 0;
  double score = 0;
  int logit = 0;
  return infer(features, index, score, logit) ? index : UINT32_MAX;
}

inline void reportBenchmark(Print &out) {
  constexpr unsigned runs = 256;
  constexpr unsigned warmup = 16;
  volatile unsigned checksum = 0;
  unsigned failures = 0;
  for (unsigned i = 0; i < warmup; ++i) {
    const unsigned result = benchmarkInference({0, static_cast<int8_t>(i), 0});
    if (result == UINT32_MAX) ++failures;
    else checksum = checksum + result;
  }

  double cycleMean = 0, cycleM2 = 0;
  uint32_t cycleMax = 0;
  const int64_t batchStart = esp_timer_get_time();
  for (unsigned i = 0; i < runs; ++i) {
    const Features input{0, static_cast<int8_t>(static_cast<int>(i % 101) - 50), 0};
    const uint32_t start = esp_cpu_get_cycle_count();
    const unsigned index = benchmarkInference(input);
    asm volatile("" : : "r"(index) : "memory");
    const uint32_t cycles = esp_cpu_get_cycle_count() - start;
    if (index == UINT32_MAX) ++failures;
    else checksum = checksum + index;
    const double delta = cycles - cycleMean;
    cycleMean += delta / (i + 1);
    cycleM2 += delta * (cycles - cycleMean);
    if (cycles > cycleMax) cycleMax = cycles;
  }
  const int64_t batchUs = esp_timer_get_time() - batchStart;
  const unsigned freq = ESP.getCpuFreqMHz();
  const unsigned heapCaps = MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT;
  const esp_partition_t *app = esp_ota_get_running_partition();
  out.printf("{\"event\":\"benchmark\",\"modelVersion\":\"%s\",\"modelStatus\":\"%s\",\"runs\":%u,\"warmup\":%u,"
             "\"core\":%d,\"cpuMHz\":%u,\"cyclesMean\":%.3f,\"cyclesStd\":%.3f,\"cyclesMax\":%lu,\"batchUs\":%lld,"
             "\"checksum\":%u,\"failedInvocations\":%u,\"backend\":\"%s\",\"modelBytes\":%u,\"tensorArenaBytes\":%u,\"tensorArenaUsedBytes\":%u,"
             "\"weightsBytes\":%u,\"windowBytes\":%u,\"sketchBytes\":%u,\"flashBytes\":%u,"
             "\"appPartitionBytes\":%u,\"heapInternalTotal\":%u,\"heapInternalFree\":%u,\"heapInternalMin\":%u,"
             "\"stackFreeMin\":%u,\"psramTotal\":%u,\"psramFree\":%u}\n",
             modelVersion, modelStatus, runs, warmup, static_cast<int>(xPortGetCoreID()), freq,
             cycleMean, sqrt(cycleM2 / (runs - 1)), static_cast<unsigned long>(cycleMax), static_cast<long long>(batchUs),
             static_cast<unsigned>(checksum), failures, inferenceBackend, modelBytes, arenaBytes, arenaUsedBytes(),
             weightsBytes, static_cast<unsigned>(sizeof(SampleWindow)),
             static_cast<unsigned>(ESP.getSketchSize()), static_cast<unsigned>(ESP.getFlashChipSize()),
             app ? static_cast<unsigned>(app->size) : 0,
             static_cast<unsigned>(heap_caps_get_total_size(heapCaps)), static_cast<unsigned>(heap_caps_get_free_size(heapCaps)),
             static_cast<unsigned>(heap_caps_get_minimum_free_size(heapCaps)), static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)),
             static_cast<unsigned>(ESP.getPsramSize()), static_cast<unsigned>(ESP.getFreePsram()));
}

}  // namespace agroedge
