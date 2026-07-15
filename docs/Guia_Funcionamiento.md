# Guía de Funcionamiento del Sistema
## Verificación de Integridad de Datos IoT con IOTA

---

## ¿Qué hace este sistema?

Imagine que tiene un sensor en una habitación que mide temperatura y humedad cada dos segundos. Esos datos viajan por una red hasta un servidor que los guarda. Pero, ¿cómo sabe que nadie modificó esos datos en el camino, o después de que llegaron?

Este sistema resuelve ese problema. Cada vez que llega una lectura de un sensor, el sistema calcula una huella digital (llamada hash) de esos datos y la guarda en una red descentralizada llamada IOTA Tangle, que funciona como un registro público e inmutable. Nadie puede modificar lo que ya está registrado ahí.

Más tarde, si alguien quiere verificar que los datos de un sensor son auténticos, el sistema vuelve a calcular la huella digital de esos datos y la compara con la que está guardada en el Tangle. Si coinciden, los datos son íntegros. Si no coinciden, alguien los modificó.

---

## Las cuatro fases del sistema

El sistema funciona en cuatro fases que se ejecutan en orden. Cada una tiene una responsabilidad específica.

### Fase 1 — El simulador de sensores

**¿Qué hace?** Como no hay sensores físicos reales, esta fase simula uno. Genera lecturas de temperatura (entre 15 °C y 35 °C) y humedad (entre 30 % y 80 %) con valores aleatorios, y las envía por la red cada dos segundos.

**¿Cómo las envía?** Usa un protocolo llamado MQTT, que es el estándar de comunicación para dispositivos IoT. Funciona como un sistema de mensajería: hay un canal llamado `iot/sensors` y el simulador publica sus lecturas ahí.

Ejemplo de lo que genera:

```json
{
  "sensor_id": "sensor_01",
  "timestamp": "2026-05-31T16:26:53Z",
  "temperature": 24.7,
  "humidity": 61.3
}
```

**¿Qué necesita para funcionar?** Que el broker MQTT (Mosquitto) esté corriendo. El broker es como un cartero: recibe los mensajes del simulador y los entrega a quien esté escuchando.

---

### Fase 2 — El procesador

**¿Qué hace?** Esta fase escucha el canal MQTT. Cada vez que llega una lectura del sensor, realiza tres pasos:

**Paso 1 — Calcular la huella digital (hash)**
Toma los datos del sensor y calcula un código SHA-256. Este código tiene siempre 64 caracteres y es único para cada combinación de datos. Si cambia aunque sea un decimal de la temperatura, el código cambia completamente.

Ejemplo de hash:
```
73bd07f0ebeac352323512be4b2d894365c29e447b72edd3b5125321cd6dd033
```

**Paso 2 — Preparar lo que va al Tangle**
Hay un principio de privacidad importante: los valores reales de temperatura y humedad nunca salen del servidor local. Lo único que se envía al Tangle es:

- La huella digital (hash)
- El identificador del sensor
- La fecha y hora de la lectura

Así se protegen los datos sensibles y solo se publica la "prueba" de que existieron.

**Paso 3 — Guardar en el registro local**
Antes de intentar publicar en el Tangle, el sistema guarda todo en un archivo local llamado `local_registry.json`. Cada entrada tiene un estado:

| Estado | Significado |
|---|---|
| `pending` | La lectura llegó y se hasheó, pero todavía no se publicó en el Tangle |
| `registered` | Se publicó exitosamente en el Tangle y se tiene el block_id |
| `failed` | Falló la publicación después de varios intentos |

---

### Fase 3 — El registro en el Tangle

**¿Qué hace?** Publica la huella digital en la red IOTA. El Tangle es una red distribuida donde una vez que se escribe algo, no se puede modificar ni eliminar.

El sistema intenta publicar hasta 4 veces con esperas progresivas (1s, 3s, 9s) antes de marcar la entrada como fallida.

Cuando la publicación es exitosa, el Tangle devuelve un identificador único llamado `block_id`. Ese `block_id` queda guardado en el registro local junto a la entrada correspondiente.

Ejemplo de block_id:
```
0xeb773875e763ef95992c82af4edc796a82697ddda738dc4b67dfe8a8609e4657
```

**¿Qué necesita para funcionar?** Un nodo de la red IOTA al que conectarse. En este proyecto se usa un nodo local levantado con Docker en `http://localhost:14265`.

---

### Fase 4 — El verificador

**¿Qué hace?** Dado un `block_id`, verifica si los datos originales siguen siendo íntegros. El proceso es:

1. Va al Tangle y recupera la huella digital que fue registrada originalmente
2. Toma los datos guardados en el registro local
3. Vuelve a calcular la huella digital de esos datos
4. Compara las dos huellas

- Si coinciden → los datos no fueron tocados → veredicto: **INTEGRO**
- Si no coinciden → alguien modificó los datos → veredicto: **ALTERADO**
- Si no puede acceder al Tangle → veredicto: **ERROR**

Este mecanismo detecta cualquier alteración, por mínima que sea. Cambiar un decimal en la temperatura produce una huella digital completamente diferente.

---

## Los archivos del sistema

### `src/simulator/sensor_simulator.py`
El simulador de sensores. Genera lecturas sintéticas de temperatura y humedad con valores aleatorios y las publica en el canal MQTT cada dos segundos. Se ejecuta con `make simulate`.

### `src/processor/mqtt_subscriber.py`
El orquestador principal del sistema. Está permanentemente escuchando el canal MQTT. Cuando llega un mensaje, coordina todo el flujo: llama al generador de hash, construye el payload, guarda en el registro local, publica en el Tangle y actualiza el estado de la entrada. Se ejecuta con `make subscribe`.

### `src/processor/hash_generator.py`
El generador de huellas digitales. Contiene dos funciones críticas:
- `canonical_json`: convierte los datos a un formato estándar antes de hashear
- `generate_hash`: aplica el algoritmo SHA-256 y devuelve el código de 64 caracteres

### `src/processor/payload_builder.py`
El constructor del payload para el Tangle. Recibe los datos completos del sensor y devuelve solo lo que puede salir al exterior: `{hash, sensor_id, timestamp}`. La temperatura y la humedad reales nunca salen de aquí. Es la frontera de privacidad del sistema.

### `src/processor/local_registry.py`
El registro local persistente. Maneja el archivo `data/local_registry.json`. Las escrituras son atómicas para evitar corrupción si el proceso se interrumpe.

### `src/iota/iota_client.py`
El conector con la red IOTA. Gestiona la conexión al nodo IOTA con importación "lazy" del SDK (solo se carga cuando realmente se necesita).

### `src/iota/tangle_writer.py`
El escritor y lector del Tangle. Tiene dos responsabilidades:
- `register_in_tangle`: publica un payload en el Tangle con reintentos automáticos y devuelve el `block_id`
- `fetch_block_data`: dado un `block_id`, recupera del Tangle el payload registrado

### `src/verifier/integrity_checker.py`
El verificador de integridad. Recupera el hash del Tangle, recalcula el hash de los datos locales, los compara y emite el veredicto.

### `verify_cli.py`
La interfaz de línea de comandos del verificador. Recibe el `block_id` por parámetro y muestra el resultado en pantalla. Se ejecuta con `make verify BLOCK_ID=0x...`. Códigos de salida: `0` = INTEGRO, `1` = ALTERADO, `2` = error.

---

## Configuración del sistema (`.env`)

| Variable | Para qué sirve |
|---|---|
| `MQTT_BROKER` | Dirección del broker MQTT (por defecto: localhost) |
| `MQTT_PORT` | Puerto del broker (por defecto: 1883) |
| `MQTT_TOPIC` | Canal de mensajes (por defecto: iot/sensors) |
| `IOTA_NODE_URL` | Dirección del nodo IOTA (por defecto: http://localhost:14265) |
| `IOTA_TAG` | Etiqueta para identificar los bloques en el Tangle |
| `LOCAL_REGISTRY_PATH` | Ruta del archivo de registro local |

---

## El registro local (`data/local_registry.json`)

Archivo JSON que crece con cada lectura procesada. Cada entrada contiene:

| Campo | Contenido |
|---|---|
| `sensor_id` | Identificador del sensor |
| `timestamp` | Fecha y hora exacta de la lectura |
| `raw_data` | Los datos originales completos |
| `hash` | La huella digital SHA-256 |
| `tangle_payload` | Lo que fue publicado en el Tangle |
| `block_id` | El identificador del bloque en el Tangle |
| `status` | Estado: `pending`, `registered` o `failed` |

---

## El flujo completo

```
[Sensor]                  [Procesador]              [Tangle IOTA]
   |                           |                          |
   |-- lectura (MQTT) -------> |                          |
   |                           |-- calcula hash           |
   |                           |-- guarda en registry     |
   |                           |-- publica hash --------> |
   |                           |<-- block_id ------------ |
   |                           |-- actualiza registry     |

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

Esta fase no forma parte del flujo normal del sistema. Es una capa de medición y prueba que se ejecuta aparte para demostrar con números reales que el sistema funciona correctamente.

### `benchmarks/measure_latency.py` — ¿Qué tan rápido es el sistema?

Repite el ciclo completo de registro y verificación N veces (por defecto 100) y cronometra cada paso. Mide dos tiempos:

- **T_reg** — milisegundos que tarda en publicar la huella digital en el Tangle
- **T_ver** — milisegundos que tarda en recuperar el bloque y emitir el veredicto

Resultado en `docs/results/latencies.csv`.

### `benchmarks/run_scenarios.py` — ¿El sistema detecta las alteraciones?

Evalúa seis escenarios diseñados para comprobar que el sistema detecta cualquier tipo de manipulación:

| Escenario | Qué hace | Resultado esperado |
|---|---|---|
| E1 | Verifica los datos sin modificar nada | INTEGRO |
| E2 | Modifica la temperatura en +1.0 °C | ALTERADO |
| E3 | Cambia el timestamp a una fecha futura | ALTERADO |
| E4 | Cambia el nombre del sensor agregando `_FAKE` | ALTERADO |
| E5 | Intenta verificar con un block_id inexistente | ERROR manejado |
| E6 | Modifica la humedad en +5.0 | ALTERADO |

Resultado en `docs/results/scenarios.csv`.

### `benchmarks/analyze_results.py` — Estadísticas y gráficos

Lee los dos CSV anteriores y produce:
- `docs/results/summary.txt` — resumen estadístico con media, mediana, percentil 95, mínimo y máximo
- `docs/results/figures/latency_histogram.png` — histogramas de T_reg y T_ver
- `docs/results/figures/latency_boxplot.png` — diagrama de cajas comparativo

### Orden de ejecución

```bash
make bench-latency      # 1º: genera latencies.csv
make bench-scenarios    # 2º: genera scenarios.csv
make bench-analyze      # 3º: genera summary.txt y figuras
```

---

## Las librerías del proyecto

| Librería | Versión | Para qué se usa |
|---|---|---|
| `paho-mqtt` | 2.1.0 | Comunicación MQTT entre el simulador y el procesador |
| `python-dotenv` | 1.0.1 | Lectura del archivo de configuración `.env` |
| `iota-sdk` | 1.1.3 | Conexión con la red IOTA (publicar y recuperar bloques) |
| `matplotlib` | 3.8+ | Generación de gráficos en la fase de benchmarks |
| `pytest` | 8.0.0 | Ejecución de pruebas automatizadas |
| `pytest-cov` | 5.0.0 | Medición de cobertura de tests |

### Librerías estándar de Python (sin instalación adicional)

| Librería | Para qué se usa |
|---|---|
| `hashlib` | Calcula el hash SHA-256 |
| `json` | Serializa y deserializa datos JSON |
| `logging` | Registra mensajes de actividad en consola |
| `time` | Controla las esperas entre reintentos |
| `datetime` | Genera marcas de tiempo en formato ISO 8601 |
| `pathlib` | Maneja rutas de archivos |
| `tempfile` | Crea archivos temporales para escrituras atómicas |
| `argparse` | Procesa argumentos de línea de comandos |
| `random` | Genera valores aleatorios de temperatura y humedad |

---

## Infraestructura necesaria

Para que el sistema funcione de extremo a extremo se necesitan tres servicios activos:

| Servicio | Para qué | Cómo arrancarlo |
|---|---|---|
| Mosquitto | Broker MQTT | `mosquitto -v` |
| Private Tangle (Docker) | Nodo IOTA local | `./run.sh 4` desde `hornet/private_tangle/` |
| El subscriber | Procesa y registra los mensajes | `make subscribe` |

El simulador (`make simulate`) puede arrancarse después para generar lecturas, y el verificador (`make verify BLOCK_ID=...`) puede usarse en cualquier momento una vez que haya entradas con `status=registered` en el registro.
