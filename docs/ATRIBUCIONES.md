# Licencias y atribuciones

## Fuentes meteorológicas

| Fuente | Uso y atribución |
| --- | --- |
| NOAA Climate Prediction Center | Boletín ENSO publicado en español. Se conserva la fuente, fecha, huella y captura de referencia para las pruebas. [Discusión ENSO de NOAA CPC](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc_Sp.shtml) |
| Eltiempoen.net | Captura HTML de la ficha pública de Toca. El dashboard atribuye el resultado a la página original y conserva hora y procedencia. El lector mantiene `robots.txt`, intervalo interno y restricciones HTTP, conforme a la verificación del proyecto. [Toca](https://eltiempoen.net/colombia/el-tiempo-en-toca) · [Metodología](https://eltiempoen.net/metodologia) · [Aviso legal](https://eltiempoen.net/aviso-legal) · [API para desarrolladores](https://eltiempoen.net/desarrolladores) |
| Open-Meteo | Consultas API para contexto y pronóstico. Los archivos del piloto conservan las fuentes de pronóstico histórico, corridas anteriores y reanálisis. La ficha de Toca atribuye a Open-Meteo datos de modelos bajo CC BY 4.0 y las licencias de cada fuente. [Documentación](https://open-meteo.com/en/docs) · [Condiciones](https://open-meteo.com/en/terms) |

## Dependencias incluidas y referenciadas

- La distribución incluye el código de las bibliotecas Arduino Chirale_TensorFLowLite 2.0.0, Adafruit BMP280 Library 3.0.0, Adafruit BusIO 1.17.4 y Adafruit Unified Sensor 1.1.15. Las licencias originales se conservan junto a cada biblioteca en `hardware/dependencias/`. [Chirale](https://github.com/spaziochirale/Chirale_TensorFlowLite) · [BMP280](https://github.com/adafruit/Adafruit_BMP280_Library) · [BusIO](https://github.com/adafruit/Adafruit_BusIO) · [Unified Sensor](https://github.com/adafruit/Adafruit_Sensor)
- Las dependencias npm se identifican en `package.json` y `package-lock.json`, y conservan sus licencias respectivas. Requests, BeautifulSoup y PySerial se declaran en los archivos `requirements.txt`. El cliente Java utiliza Gson 2.15.0. [Gson](https://github.com/google/gson)
- La caracterización de energía utiliza la documentación de la ESP32-S3 y la latencia medida del modelo. [Espressif ESP32-S3 Series Datasheet v2.2](https://documentation.espressif.com/esp32_s3_datasheet_en.pdf)

Las bitácoras y los datos propios se entregan para la evaluación académica del proyecto. Su inclusión no asigna una licencia de publicación a esos datos.
