# AgroEdge IA

Estación agroclimática universitaria para Toca, Boyacá. La aplicación adapta la beta de DataCity AI y reutiliza su estructura Next.js y React, barra lateral, tarjetas, gráficas Recharts, cálculos estadísticos, detección de anomalías y análisis temporal.

## Versión 0.2.1 · Extracción del boletín con BeautifulSoup

El módulo R5 utiliza Requests para consultar el HTML por HTTPS y BeautifulSoup (`bs4`) para extraer y limpiar el texto del que se obtienen la fecha, el estado ENSO y la sinopsis. Si ya ejecutaste la versión 0.2.0, vuelve a instalar las dependencias de `scraper/requirements.txt` en tu entorno Python para incorporar BeautifulSoup.

El 22 de noviembre de 2026 pasaron las nueve pruebas de R5 con BeautifulSoup 4.14.3 y la comprobación del panel con el boletín recién extraído. [Resultados y comandos de verificación](docs/r5-verificacion.md#versión-021)

## Boletín agroclimático externo

El panel principal muestra la discusión mensual del ENSO en español, su fecha de publicación y un enlace al Climate Prediction Center de NOAA. Incluye la edición archivada del 12 de noviembre de 2026 para poder abrir el panel sin Internet. Al recopilar o sincronizar una edición, el panel lee el archivo local de boletines. El botón **Ver lluvia prevista en Toca** abre el pronóstico de Open-Meteo de 24 y 48 horas.

Extrae esta versión en una carpeta nueva. La base de los sensores continúa en la instalación que ya utilizas. Para consultar el mismo historial desde la nueva versión, detén la instancia anterior, conserva una copia de seguridad de su carpeta de datos y configura `AGROEDGE_DB` en `.env.local` con la ruta absoluta al archivo existente. Ejecuta una sola instancia de la aplicación sobre esa base. Para el ESP32-S3 con AHT20 y BMP280 puedes conservar el firmware que ya transmite las mediciones. Los sketches de ejemplo del ZIP anterior se conservan para quienes usan BME280.

En la terminal de VS Code, desde la carpeta que contiene `package.json`, puedes reproducir la extracción de la edición incluida y después consultar la web con Python 3.10 o superior.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scraper\requirements.txt
.\.venv\Scripts\python.exe scraper\agroclima.py capture tests\fixtures\noaa-enso-es-2026-11-12.html
.\.venv\Scripts\python.exe scraper\agroclima.py fetch
.\.venv\Scripts\python.exe scraper\agroclima.py status
```

Los boletines se guardan en `data/agroclima.sqlite`. El panel relee esa base cada minuto mientras está abierto. Si ya tienes instalado el proyecto anterior, sigue los pasos de ejecución de Windows de abajo en la carpeta nueva. La documentación R5 incluye la consulta periódica, la sincronización, las pruebas y el alcance de la verificación. [Guía R5](docs/r5.md) · [Evidencia de verificación](docs/r5-verificacion.md)

## Cambios de la versión 0.1.1

- Al cambiar de modo o filtro, la aplicación descarta las respuestas de consultas anteriores. La lectura destacada de Alertas pertenece al periodo seleccionado.
- La adquisición rechaza declaraciones de procedencia incompatibles con el transporte. Reintentar una misma prueba por un canal distinto genera un conflicto de registro.
- La actualización admite la base SQLite y las exportaciones CSV y Excel de la versión 0.1.0. Para trasladar el historial a otra carpeta, detén el servidor y copia `data/agroedge.sqlite` junto a los demás archivos de `data` que existan.

## Ejecutar en Windows con VS Code

1. Instala **Node.js 24 LTS** (24.14 o posterior). Instala también Python 3 para usar el puente USB y reproducir la prueba serial.
2. Extrae el ZIP. En VS Code abre la carpeta `AgroEdge-IA`, donde está `package.json`.
3. En una terminal PowerShell de VS Code ejecuta:

   ```powershell
   node --version
   npm.cmd ci
   npm.cmd run dev
   ```

4. Abre [http://127.0.0.1:5173](http://127.0.0.1:5173). Selecciona **Simulación**, elige un escenario y pulsa **Iniciar**. El historial se crea conforme llegan registros. Para cargar los ejemplos incluidos, entra en **Historial y registros** y usa **Importar archivo**.
5. Para verificar una compilación de producción, detén el servidor de desarrollo y ejecuta:

   ```powershell
   npm.cmd run check
   npm.cmd run build
   npm.cmd run start
   ```

`npm.cmd` evita depender de la política de ejecución de scripts PowerShell de Windows. La base se crea en `data/agroedge.sqlite`. Usa el mismo directorio de trabajo cada vez. Para hacer una copia de la base, detén primero el servidor y copia la carpeta `data` completa.

## Modos

| Modo | Cómo funciona | Etiqueta del registro |
| --- | --- | --- |
| Simulación | Elige escenario, semilla, intervalo y amplitud. Iniciar o reiniciar abre una sesión. Pausar y reanudar conserva la misma secuencia. Cambiar la velocidad modifica el intervalo, sin cambiar la progresión de valores de esa sesión. | `SIMULATION` y `SIMULATED` |
| USB | Instala el puente de Python, conecta Arduino UNO o ESP32, cierra el monitor serial del IDE y selecciona el puerto COM en el panel. | `USB` y `REAL` |
| Wi-Fi | Activa recepción LAN y envía JSON desde el ESP32 a la IP local real del equipo. | `WIFI` y `REAL` |

El simulador genera conforme el panel está abierto y consultando la estación. Tras cerrar el panel o suspender el equipo, retoma en el momento actual sin agregar un historial ficticio durante la desconexión. La semilla, el escenario y la amplitud reproducen los valores por ordinal. Las fechas e identificadores de cada sesión se asignan al ejecutarla.

En el historial puedes seleccionar estación, sesión, fechas y calidad. Las fechas del filtro se interpretan en Colombia y el día final es inclusivo. Los archivos conservan fecha UTC, fuente y orden. Al seleccionar columnas, Excel oculta la columna de recuperación y CSV la adjunta al final, de modo que un archivo parcial también puede recuperar el registro íntegro. El ZIP trae un CSV y un XLSX de demostración generados por la aplicación.

## Configurar USB

```powershell
python --version
python -m pip install -r hardware/requirements.txt
```

En **Adquisición por USB** pulsa **Buscar puertos**, selecciona el COM y conecta a **115200 baudios** si usas el ejemplo. Si Python no está en PATH, configura `AGROEDGE_PYTHON` con la ruta absoluta de `python.exe`. El puente lee una línea JSON por muestra y trata de restablecer la conexión si se pierde el puerto. La aplicación muestra la última recepción, los errores y el tiempo sin comunicación. La recepción USB funciona con el servicio local y Python.

## Configurar Wi-Fi en la red del proyecto

1. Crea `.env.local` a partir de `.env.example`. Asigna a `AGROEDGE_DEVICE_TOKEN` un valor aleatorio largo y conserva el mismo valor en el firmware o servicio Java. Puedes generar un token en la terminal con `node -e "console.log(require('node:crypto').randomBytes(32).toString('hex'))"`.
2. Conecta computador y ESP32 a la misma red local. Ejecuta `ipconfig` y copia la dirección **IPv4 del adaptador conectado a esa red**. Si Windows solicita permiso de red para el servidor, utiliza el perfil de red privada y limita el puerto 5173 a la red del laboratorio.
3. Ejecuta `npm.cmd run dev:lan` o, después de compilar, `npm.cmd run start:lan`. Accede al panel desde `http://127.0.0.1:5173` en el mismo equipo. Usa la IPv4 encontrada en la URL del firmware ESP32.
4. En Arduino IDE instala la biblioteca **Adafruit BME280 Library** y sus dependencias. Abre el ejemplo de la carpeta de hardware correspondiente. En ESP32 configura red, puerto, token e ID de estación. En el UNO el puente asigna la hora de recepción. Para enviar por Wi-Fi el ESP32 sincroniza el reloj mediante NTP.

Usa la recepción HTTP de ejemplo dentro de la red privada del laboratorio. El token viaja por HTTP en la configuración LAN y el filtro de nombre de host del panel es una comodidad local. Mantén el puerto fuera de Internet. Si cambias de red, confirma la IP y el acceso al puerto antes de reiniciar el ESP32.

## Pronóstico y alertas

El panel consulta [Open-Meteo](https://open-meteo.com/en/docs) por HTTPS. El punto inicial es la cabecera de Toca, tomado de la [Registraduría](https://registraduria.gov.co/IMG/pdf/20231006_puestos-de-votacion-georreferenciacion_territoriales.pdf). Si se conoce la ubicación del lote, se puede configurar en `AGROEDGE_LAT` y `AGROEDGE_LON`. El pronóstico se resume en bloques horarios de 24 y 48 h a partir del inicio de la hora actual. La consulta requiere Internet y la interfaz informa si no está disponible. Las alertas de calidad usan datos de la estación. Los avisos de precipitación identifican su fuente externa y son orientativos.

## Verificación y estructura

```powershell
npm.cmd test
npm.cmd run check
npm.cmd run build
npm.cmd run test:app
```

La prueba de aplicación abre un servidor de producción y una base temporal propios. Usa Python para el fixture serial. Si el entorno de ejecución bloquea las conexiones a `127.0.0.1`, ejecuta `npm.cmd run test:app -- --routes` después de compilar para verificar las rutas compiladas directamente. Lee el [contrato de integración](docs/integracion.md) y el [registro de verificación](docs/verificacion.md).

| Carpeta | Contenido |
| --- | --- |
| `app`, `components` | Interfaz Next.js y endpoints locales. |
| `lib` | Modelo de datos, SQLite, simulación, análisis y formatos. |
| `hardware` | Puente serial local y ejemplos Arduino UNO y ESP32. |
| `examples` | Archivos de demostración y fixtures de transporte. |
| `tests`, `scripts` | Pruebas de lógica y ejecución completa. |
| `docs` | Contrato para Java, ESP32, formatos y verificación. |

El repositorio de esta entrega es independiente. El respaldo íntegro de DataCity AI se conservó por separado. Se mantuvieron el panel, las gráficas, las estadísticas, la detección de anomalías, Pearson, la tendencia local y la exploración de registros. La demo masiva y la imputación se reemplazaron por la simulación reproducible y las banderas de calidad. Las vistas genéricas de la feria y la configuración de gas MQ se retiraron al adaptar la estación al BME280. El módulo de consultas conserva preguntas predeterminadas sobre las mediciones. La adquisición, persistencia y consulta pueden pasar al servicio Java cuando esté disponible, usando el contrato adjunto.

