#pragma once

#include "classifier.h"

#if !__has_include("tflm_model_data.h")
#error "Falta tflm_model_data.h del modelo definitivo exposure-tflm-2c4870d61d3f."
#endif

#include <Chirale_TensorFlowLite.h>
#include <tensorflow/lite/micro/micro_interpreter.h>
#include <tensorflow/lite/micro/micro_mutable_op_resolver.h>
#include <tensorflow/lite/schema/schema_generated.h>
#include <math.h>
#include <string_view>

#include "tflm_model_data.h"

namespace agroedge {

static_assert(std::string_view(modelVersion) == "exposure-tflm-2c4870d61d3f", "Version del modelo TinyML incorrecta.");
static_assert(sizeof(modelFlatbuffer) == 1160, "Tamano del modelo TinyML incorrecto.");
constexpr char inferenceBackend[] = "TFLITE_MICRO";
constexpr unsigned modelBytes = sizeof(modelFlatbuffer);
constexpr unsigned weightsBytes = 0;  // Weights are serialized inside the FlatBuffer.
alignas(16) inline uint8_t tensorArena[4096];
constexpr unsigned arenaBytes = sizeof(tensorArena);

inline tflite::MicroInterpreter *interpreter = nullptr;
inline TfLiteTensor *inputTensor = nullptr;
inline TfLiteTensor *outputTensor = nullptr;

inline bool beginInference() {
  static tflite::MicroMutableOpResolver<1> ops;
  const auto *model = tflite::GetModel(modelFlatbuffer);
  if (model->version() != TFLITE_SCHEMA_VERSION || ops.AddFullyConnected() != kTfLiteOk) return false;
  static tflite::MicroInterpreter runner(model, ops, tensorArena, arenaBytes);
  if (runner.AllocateTensors() != kTfLiteOk) return false;
  auto *input = runner.input(0);
  auto *output = runner.output(0);
  if (!input || !output || input->type != kTfLiteInt8 || output->type != kTfLiteInt8 ||
      input->bytes != 3 || output->bytes != 1 || input->params.scale <= 0 || output->params.scale <= 0) return false;
  inputTensor = input;
  outputTensor = output;
  interpreter = &runner;
  return true;
}

inline unsigned arenaUsedBytes() { return interpreter ? interpreter->arena_used_bytes() : 0; }

inline int8_t encodeFeature(int8_t feature) {
  const long q = lroundf(static_cast<float>(feature) / inputTensor->params.scale) + inputTensor->params.zero_point;
  return static_cast<int8_t>(q < -128 ? -128 : q > 127 ? 127 : q);
}

inline bool infer(Features features, unsigned &index, double &score, int &logit) {
  if (!interpreter) return false;
  inputTensor->data.int8[0] = encodeFeature(features.temperature);
  inputTensor->data.int8[1] = encodeFeature(features.humidity);
  inputTensor->data.int8[2] = encodeFeature(features.pressureChange);
  if (interpreter->Invoke() != kTfLiteOk) return false;
  logit = outputTensor->data.int8[0];
  const int margin = logit - outputTensor->params.zero_point;
  index = margin > 0 ? 1 : 0;
  score = (margin < 0 ? -margin : margin) / 255.0;
  return true;
}

}  // namespace agroedge
