#pragma once

#include "classifier.h"

namespace agroedge {

// Engineering reference points only. No field observations were used to set them.
constexpr char modelVersion[] = "humidity-prototype-1";
constexpr char modelStatus[] = "PRELIMINARY";
constexpr char labelText[][32] = {"Humedad ambiental baja", "Humedad ambiental media", "Humedad ambiental alta"};
constexpr Features centroids[] = {{0, -15, 0}, {0, 10, 0}, {0, 35, 0}};

}  // namespace agroedge
