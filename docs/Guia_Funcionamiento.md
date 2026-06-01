# Guía de Funcionamiento del Sistema
## Verificación de Integridad de Datos IoT con IOTA

---

## ¿Qué hace este sistema?

Imaginá que tenés un sensor en una habitación que mide temperatura y humedad cada dos segundos. Esos datos viajan por una red hasta un servidor que los guarda. Pero, ¿cómo sabés que nadie modificó esos datos en el camino, o después de que llegaron?

Este sistema resuelve ese problema. Cada vez que llega una lectura de un sensor, el sistema calcula una **huella digital** (llamada hash) de esos datos y la guarda en una red descentralizada llamada **IOTA Tangle**, que funciona como un registro público e inmutable. Nadie puede modificar lo que ya está registrado ahí.

Más tarde, si alguien quiere verificar que los datos de un sensor son auténticos, el sistema vuelve a calcular la huella digital de esos datos y la compara con la que está guardada en el Tangle. Si coinciden, los datos son íntegros. Si no coinciden, alguien los modificó.

---

## Las cuatro fases del sistema

El sistema funciona en cuatro fases que se ejecutan en orden. Cada una tiene una responsabilidad específica.

---

### Fase 1 — El simulador de sensores

**¿Qué hace?**
Como no hay sensores físicos reales, esta fase simula uno. Genera lecturas de temperatura (entre 15°C y 35°C) y humedad (entre 30% y 80%) con valores aleatorios, y las envía por la red cada dos segundos.

**¿Cómo las envía?**
Usa un protocolo llamado **MQTT**, que es el estándar de comunicación para dispositivos IoT. Funciona como un sistema de mensajería: hay un "canal" llamado `iot/sensors` y el simulador publica sus lecturas ahí.

**Ejemplo de lo que genera:**
```
{
  "sensor_id": "sensor_01",
  "timestamp": "2026-05-31T16:26:53Z",
  "temperature": 24.7,
  "humidity": 61.3
}
```

**¿Qué necesita para funcionar?**
Que el broker MQTT (Mosquitto) esté corriendo. El broker es como un cartero: recibe los mensajes del simulador y los entrega a quien esté escuchando.

---

### Fase 2 — El procesador

**¿Qué hace?**
Esta fase "escucha" el canal MQTT. Cada vez que llega una lectura del sensor, realiza tres pasos:

**Paso 1 — Calcular la huella digital (hash)**
Toma los datos del sensor y calcula un código SHA-256. Este código tiene siempre 64 caracteres y es único para cada combinación de datos. Si cambia aunque sea un decimal de la temperatura, el código cambia completamente. Es prácticamente imposible que dos lecturas distintas generen el mismo código.

Ejemplo de hash:
```
73bd07f0ebeac3523235 12be4b2d894365c29e447b72edd3b5125321cd6dd033
```

**Paso 2 — Preparar lo que va al Tangle**
Hay un principio de privacidad importante: los valores reales de temperatura y humedad **nunca salen del servidor local**. Lo único que se envía al Tangle es:
- La huella digital (hash)
- El identificador del sensor
- La fecha y hora de la lectura

Así se protegen los datos sensibles y solo se publica la "prueba" de que existieron.

**Paso 3 — Guardar en el registro local**
Antes de intentar publicar en el Tangle, el sistema guarda todo en un archivo local llamado `local_registry.json`. Cada entrada tiene un estado que puede ser:

| Estado | Significado |
|--------|-------------|
| `pending` | La lectura llegó y se hasheó, pero todavía no se publicó en el Tangle |
| `registered` | Se publicó exitosamente en el Tangle y se tiene el `block_id` |
| `failed` | Falló la publicación después de varios intentos |

---

### Fase 3 — El registro en el Tangle

**¿Qué hace?**
Publica la huella digital en la red IOTA. El Tangle es una red distribuida donde una vez que se escribe algo, **no se puede modificar ni eliminar**. Esto es lo que garantiza la integridad del sistema.

El sistema intenta publicar hasta 4 veces con esperas progresivas (1s, 3s, 9s) antes de marcar la entrada como fallida.

Cuando la publicación es exitosa, el Tangle devuelve un identificador único llamado **block_id**, que es como el número de recibo de la operación. Ese `block_id` queda guardado en el registro local junto a la entrada correspondiente.

Ejemplo de `block_id`:
```
0xeb773875e763ef95992c82af4edc796a82697ddda738dc4b67dfe8a8609e4657
```

**¿Qué necesita para funcionar?**
Un nodo de la red IOTA al que conectarse. En este proyecto se usa un nodo local levantado con Docker (en `http://localhost:14265`).

---

### Fase 4 — El verificador

**¿Qué hace?**
Dada un `block_id`, verifica si los datos originales siguen siendo íntegros. El proceso es:

1. Va al Tangle y recupera la huella digital que fue registrada originalmente
2. Toma los datos guardados en el registro local
3. Vuelve a calcular la huella digital de esos datos
4. Compara las dos huellas

**Si coinciden** → los datos no fueron tocados → veredicto: **INTEGRO**

**Si no coinciden** → alguien modificó los datos → veredicto: **ALTERADO**

**Si no puede acceder al Tangle** → veredicto: **ERROR**

Este mecanismo detecta cualquier alteración, por mínima que sea. Cambiar un decimal en la temperatura produce una huella digital completamente diferente.

---

## Los archivos del sistema

A continuación se explica qué hace cada archivo que participa en la ejecución del sistema. Se omiten los archivos de tests, configuración y benchmarks.

---

### `src/simulator/sensor_simulator.py`
**El simulador de sensores.**

Genera lecturas sintéticas de temperatura y humedad con valores aleatorios y las publica en el canal MQTT cada dos segundos. Simula lo que haría un sensor físico real. Se ejecuta con `make simulate`.

---

### `src/processor/mqtt_subscriber.py`
**El orquestador principal del sistema.**

Es el cerebro de las fases 2 y 3. Está permanentemente escuchando el canal MQTT. Cuando llega un mensaje, coordina todo el flujo: llama al generador de hash, construye el payload, guarda en el registro local, publica en el Tangle y actualiza el estado de la entrada. Se ejecuta con `make subscribe`.

---

### `src/processor/hash_generator.py`
**El generador de huellas digitales.**

Contiene dos funciones pequeñas pero críticas:
- `canonical_json`: convierte los datos a un formato estándar antes de hashear (garantiza que el mismo dato siempre produzca el mismo resultado sin importar el orden de los campos)
- `generate_hash`: aplica el algoritmo SHA-256 y devuelve el código de 64 caracteres

Todo el sistema depende de que el hash sea siempre calculado por este archivo. Si algo se hashea por otro camino, la verificación falla.

---

### `src/processor/payload_builder.py`
**El constructor del payload para el Tangle.**

Recibe los datos completos del sensor y devuelve solo lo que puede salir al exterior: `{hash, sensor_id, timestamp}`. La temperatura y la humedad reales nunca salen de acá. Es la frontera de privacidad del sistema.

---

### `src/processor/local_registry.py`
**El registro local persistente.**

Maneja el archivo `data/local_registry.json`. Se encarga de guardar cada entrada, buscar por hash o por block_id, y actualizar el estado cuando llega la confirmación del Tangle. Las escrituras son atómicas (usa un archivo temporal y un reemplazo instantáneo) para evitar corrupción si el proceso se interrumpe a mitad.

---

### `src/iota/iota_client.py`
**El conector con la red IOTA.**

Gestiona la conexión al nodo IOTA. Para no depender del SDK de IOTA en entornos donde no está instalado (como en pruebas), la importación del SDK se hace de forma "lazy" — solo se carga cuando realmente se necesita. También tiene funciones de conversión entre texto y el formato hexadecimal que requiere la red IOTA.

---

### `src/iota/tangle_writer.py`
**El escritor y lector del Tangle.**

Tiene dos responsabilidades:
- `register_in_tangle`: publica un payload en el Tangle con reintentos automáticos y devuelve el `block_id`
- `fetch_block_data`: dado un `block_id`, recupera del Tangle el payload que fue registrado

---

### `src/verifier/integrity_checker.py`
**El verificador de integridad.**

Contiene la lógica central de verificación: recupera el hash del Tangle, recalcula el hash de los datos locales, los compara y emite el veredicto. Distingue claramente entre un veredicto `ALTERADO` (la verificación funcionó y detectó manipulación) y un error de sistema (no se pudo conectar al Tangle, el bloque no existe, etc.).

---

### `verify_cli.py`
**La interfaz de línea de comandos del verificador.**

Es el punto de entrada para verificar manualmente una lectura. Recibe el `block_id` por parámetro, llama al verificador y muestra el resultado en pantalla. Se ejecuta con `make verify BLOCK_ID=0x...`. El código de salida del programa indica el veredicto: 0 = INTEGRO, 1 = ALTERADO, 2 = error.

---

### `.env`
**La configuración del sistema.**

Contiene las variables de entorno que el sistema lee al arrancar:

| Variable | Para qué sirve |
|----------|----------------|
| `MQTT_BROKER` | Dirección del broker MQTT (por defecto: `localhost`) |
| `MQTT_PORT` | Puerto del broker (por defecto: `1883`) |
| `MQTT_TOPIC` | Canal de mensajes (por defecto: `iot/sensors`) |
| `IOTA_NODE_URL` | Dirección del nodo IOTA (actualmente: `http://localhost:14265`) |
| `IOTA_TAG` | Etiqueta para identificar los bloques en el Tangle |
| `LOCAL_REGISTRY_PATH` | Ruta del archivo de registro local |

---

### `data/local_registry.json`
**El registro local de todas las lecturas.**

Es un archivo JSON que crece con cada lectura procesada. Cada entrada contiene:

| Campo | Contenido |
|-------|-----------|
| `sensor_id` | Identificador del sensor que generó la lectura |
| `timestamp` | Fecha y hora exacta de la lectura |
| `raw_data` | Los datos originales completos (temperatura, humedad, etc.) |
| `hash` | La huella digital SHA-256 de esos datos |
| `tangle_payload` | Lo que fue publicado en el Tangle (hash + sensor_id + timestamp) |
| `block_id` | El identificador del bloque en el Tangle (null si no fue publicado) |
| `status` | Estado actual: `pending`, `registered` o `failed` |

---

## El flujo completo en una imagen

```
[Sensor]                  [Procesador]              [Tangle IOTA]
   |                           |                          |
   |-- lectura (MQTT) -------> |                          |
   |                           |-- calcula hash           |
   |                           |-- guarda en registry     |
   |                           |-- publica hash --------> |
   |                           |<-- block_id ------------ |
   |                           |-- actualiza registry     |
   |                           |                          |

[Verificador] (más tarde, cuando se quiere comprobar)
   |
   |-- pide bloque por block_id -----------------------> |
   |<-- hash guardado ---------------------------------- |
   |-- recalcula hash de los datos locales
   |-- compara: ¿coinciden?
   |     SI -> INTEGRO
   |     NO -> ALTERADO
```

---

## Fase 5 — Benchmarks y validación

Esta fase no forma parte del flujo normal del sistema (simulador → procesador → Tangle → verificador). Es una capa de **medición y prueba** que se ejecuta aparte para demostrar, con números reales, que el sistema funciona correctamente y con qué rendimiento.

Tiene tres herramientas que se usan en secuencia.

---

### `benchmarks/measure_latency.py` — ¿Qué tan rápido es el sistema?

Repite el ciclo completo de registro y verificación N veces (por defecto 100) y cronometra cada paso. Mide dos tiempos:

- **T_reg** — cuántos milisegundos tarda en publicar la huella digital en el Tangle y recibir el `block_id`
- **T_ver** — cuántos milisegundos tarda en recuperar ese bloque del Tangle y emitir el veredicto

Por cada iteración guarda una fila en un archivo CSV (`docs/results/latencies.csv`):

```
iteracion | sensor_id | T_reg_ms | T_ver_ms | status | block_id
```

El objetivo es tener datos reales para el TFM: "el sistema tarda en promedio X milisegundos en registrar y Y milisegundos en verificar".

---

### `benchmarks/run_scenarios.py` — ¿El sistema detecta las alteraciones?

Registra una sola lectura real en el Tangle y luego la verifica seis veces bajo condiciones distintas. Cada verificación es un escenario diseñado para comprobar que el sistema detecta cualquier tipo de manipulación:

| Escenario | Qué hace | Resultado esperado |
|-----------|----------|--------------------|
| E1 | Verifica los datos sin modificar nada | INTEGRO |
| E2 | Modifica la temperatura en +1.0°C antes de verificar | ALTERADO |
| E3 | Cambia el timestamp a una fecha futura | ALTERADO |
| E4 | Cambia el nombre del sensor agregando `_FAKE` | ALTERADO |
| E5 | Intenta verificar con un `block_id` inventado que no existe | ERROR manejado correctamente |
| E6 | Modifica la humedad en +5.0 antes de verificar | ALTERADO |

Genera un CSV (`docs/results/scenarios.csv`) con cuántos escenarios pasaron según lo esperado. Esto demuestra que el sistema detecta cualquier tipo de manipulación, por mínima que sea — incluso cambiar un solo decimal en la temperatura produce un veredicto ALTERADO.

---

### `benchmarks/analyze_results.py` — Los números y los gráficos

Lee los dos CSVs anteriores y produce tres salidas:

- **`docs/results/summary.txt`** — resumen estadístico completo con media, mediana, percentil 95, mínimo y máximo de T_reg y T_ver
- **`docs/results/figures/latency_histogram.png`** — dos histogramas que muestran cómo se distribuyen los tiempos de registro y verificación
- **`docs/results/figures/latency_boxplot.png`** — un gráfico de caja que compara visualmente las dos distribuciones

El dato más importante para el TFM es el **percentil 95 (p95)**: significa que el 95% de las operaciones terminaron en menos de X milisegundos. Es más representativo que el máximo porque descarta los picos anómalos o los momentos de congestión de la red.

---

### Orden de ejecución de los benchmarks

```bash
make bench-latency      # 1ro: genera latencies.csv (tarda varios minutos — 100 escrituras reales)
make bench-scenarios    # 2do: genera scenarios.csv
make bench-analyze      # 3ro: lee ambos CSVs y genera summary.txt + figuras
```

Los tres requieren que el private tangle esté corriendo. El primero es el más lento porque realiza 100 publicaciones reales en el Tangle.

---

## Las librerías del proyecto

Una librería es un conjunto de código ya escrito por otros que el proyecto usa para no tener que reinventar la rueda. Acá se explica qué hace cada una y por qué está en el proyecto.

---

### `paho-mqtt` (versión 2.1.0)
**El mensajero entre el simulador y el procesador.**

MQTT es el protocolo de comunicación estándar para dispositivos IoT. `paho-mqtt` es la librería que implementa ese protocolo en Python. El simulador la usa para publicar lecturas en el canal `iot/sensors`, y el subscriber la usa para escuchar ese mismo canal y recibir los mensajes.

Sin esta librería, el simulador y el procesador no podrían comunicarse.

---

### `python-dotenv` (versión 1.0.1)
**El lector de configuración.**

Lee el archivo `.env` al arrancar el sistema y convierte cada línea en una variable disponible para el código. Así, cambiar la dirección del broker MQTT o la URL del nodo IOTA no requiere tocar el código — solo se edita el `.env`.

Es una buena práctica de seguridad: las configuraciones sensibles (como URLs y credenciales) viven fuera del código y no se suben al repositorio.

---

### `iota-sdk` (versión 1.1.3)
**El conector con la red IOTA.**

Es el SDK (kit de desarrollo) oficial de la Fundación IOTA para Python. Permite conectarse a un nodo de la red IOTA y realizar operaciones como publicar bloques de datos (Tagged Data Blocks) y recuperarlos por su identificador.

Es la librería más pesada del proyecto: internamente está escrita en Rust y requiere compilar código nativo al instalarse, por eso necesita que Rust esté instalado en el sistema.

En este proyecto se usa exclusivamente para dos operaciones: publicar la huella digital en el Tangle (`build_and_post_block`) y recuperar un bloque ya publicado para verificarlo (`get_block_data`).

---

### `matplotlib` (versión 3.8 o superior)
**El generador de gráficos.**

Librería estándar de Python para crear visualizaciones. En este proyecto se usa únicamente en la fase de benchmarks (Fase 5) para generar los gráficos de latencia: histogramas y boxplots que muestran cuánto tarda el sistema en registrar una lectura en el Tangle y en verificarla.

No interviene en la ejecución normal del sistema (simulador, subscriber, verificador).

---

### `pytest` (versión 8.0.0)
**El ejecutor de pruebas.**

Framework estándar de Python para escribir y ejecutar tests automatizados. Permite verificar que cada función del sistema se comporta correctamente sin necesidad de correr el sistema completo. Los tests unitarios del proyecto usan objetos simulados (mocks) en lugar de conexiones reales a MQTT o al Tangle, lo que los hace rápidos y reproducibles.

Solo se usa durante el desarrollo, no en la ejecución normal del sistema.

---

### `pytest-cov` (versión 5.0.0)
**El medidor de cobertura de tests.**

Extensión de pytest que analiza qué porcentaje del código fue ejecutado durante los tests. Genera reportes que muestran qué líneas de código están cubiertas por al menos un test y cuáles no. El proyecto mantiene un objetivo de cobertura del 90% o más en los módulos críticos.

Al igual que pytest, solo se usa durante el desarrollo.

---

### Librerías estándar de Python (sin instalación adicional)
Las siguientes librerías vienen incluidas con Python y no requieren instalación:

| Librería | Para qué se usa en el proyecto |
|----------|-------------------------------|
| `hashlib` | Calcula el hash SHA-256 de los datos del sensor |
| `json` | Serializa y deserializa datos en formato JSON |
| `logging` | Registra mensajes de actividad en la consola |
| `os` | Lee variables de entorno y maneja rutas de archivos |
| `time` | Controla las esperas entre reintentos al publicar en el Tangle |
| `datetime` | Genera la marca de tiempo en formato estándar ISO 8601 |
| `pathlib` | Maneja rutas de archivos de forma segura entre sistemas operativos |
| `tempfile` | Crea archivos temporales para las escrituras atómicas del registro |
| `argparse` | Procesa los argumentos de línea de comandos (como `--block-id`) |
| `random` | Genera los valores aleatorios de temperatura y humedad en el simulador |

---

## ¿Qué infraestructura necesita estar corriendo?

Para que el sistema funcione de punta a punta se necesitan tres servicios activos:

| Servicio | Para qué | Cómo arrancarlo |
|----------|----------|-----------------|
| Mosquitto | Broker MQTT — el canal de mensajes | `mosquitto -v` |
| Private Tangle (Docker) | Nodo IOTA local | `./run.sh 2` desde `hornet/private_tangle/` |
| El subscriber | Procesa los mensajes y los registra | `make subscribe` |

El simulador (`make simulate`) puede arrancarse después para generar lecturas, y el verificador (`make verify BLOCK_ID=...`) puede usarse en cualquier momento una vez que haya entradas con `status=registered` en el registro.
