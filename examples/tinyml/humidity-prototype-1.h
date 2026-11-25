#pragma once

#include "classifier.h"

namespace agroedge {

// Engineering reference points used in the early USB verification.
constexpr char modelVersion[] = "humidity-prototype-1";
constexpr char modelStatus[] = "PRELIMINARY";
constexpr char labelText[][32] = {"Humedad ambiental baja", "Humedad ambiental media", "Humedad ambiental alta"};
constexpr Features centroids[] = {{0, -15, 0}, {0, 10, 0}, {0, 35, 0}};

}  // namespace agroedge
