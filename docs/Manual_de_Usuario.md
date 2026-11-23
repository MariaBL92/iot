# Manual de Usuario
## Sistema de verificación de integridad de datos IoT con IOTA

---

## 1. ¿Qué es este sistema?

Este sistema permite comprobar si unos datos recogidos por sensores —por ejemplo, lecturas de temperatura o humedad— han sido modificados después de ser registrados. Es una herramienta de detección de manipulaciones: no impide que alguien altere los datos, pero garantiza que cualquier alteración, por pequeña que sea, será detectada. El sistema es un prototipo experimental desarrollado como Trabajo Fin de Máster. No utiliza sensores físicos: los simula por software.

---

## 2. ¿Qué problema resuelve?

Cada vez más decisiones importantes se toman basándose en datos generados por dispositivos conectados (sensores ambientales, equipos médicos, cadena de frío, monitores agrícolas o industriales). En el camino desde el sensor hasta quien analiza los datos pueden ocurrir tres cosas problemáticas:

- **Manipulación intencionada.** Alguien con acceso al sistema puede modificarlos intencionadamente.
- **Alteración accidental.** Un error técnico o corrupción de datos puede alterarlos sin querer.
- **Repudio.** Alguien puede negar que un dato concreto fuera el que en su momento se registró.

Este sistema propone una alternativa a los métodos tradicionales basados en una autoridad central: utiliza una red distribuida —el Tangle de IOTA— donde los registros no pueden modificarse una vez escritos, ni siquiera por la persona que los creó.

---

## 3. ¿Cómo funciona?

El funcionamiento descansa en dos conceptos: la huella digital y el registro inmutable.

### 3.1 La huella digital (hash)

Una huella digital es un código corto que se calcula a partir del contenido de un dato. Tiene tres propiedades cruciales:

- **Determinismo.** Si dos datos son idénticos, su huella es idéntica.
- **Sensibilidad.** Si dos datos difieren en lo más mínimo las huellas son completamente diferentes.
- **Privacidad.** A partir de la huella es prácticamente imposible reconstruir el dato original.

Este sistema utiliza SHA-256, que produce huellas de 64 caracteres. Si el sensor lee 23.5 °C, la huella es una. Si ese dato se modifica a 23.6 °C, la huella ya no será la misma.

### 3.2 El registro inmutable (Tangle de IOTA)

Una vez calculada la huella, hay que guardarla donde no pueda ser alterada. Este prototipo utiliza un nodo IOTA privado que corre localmente mediante Docker. El Tangle de IOTA ofrece tres ventajas:

- **Sin costes.** Es gratuito, no cobra comisiones por escribir.
- **Orientado a IoT.** Diseñado para almacenar gran cantidad de pequeños registros.
- **Auditable.** Cualquiera puede consultar lo registrado y verificarlo de forma independiente.

> **Importante:** En el Tangle solo se guarda la huella digital, nunca el dato original. Los valores del sensor permanecen únicamente en el ordenador local.

### 3.3 La verificación

El sistema recupera la huella original del Tangle y la compara con la huella recalculada del dato actual. Si coinciden: el dato es íntegro. Si no coinciden: el dato ha sido alterado.

---

## 4. Las cuatro partes del sistema

- **Capa 1 — Simulación de sensores:** genera datos artificiales de temperatura y humedad cada pocos segundos.
- **Capa 2 — Procesamiento:** recibe esos datos, calcula su huella digital y los guarda en un registro local.
- **Capa 3 — Registro en el Tangle:** envía la huella al Tangle de IOTA, donde queda registrada de forma inmutable.
- **Capa 4 — Verificación:** dado un identificador de registro en el Tangle, recupera la huella, la compara y emite un veredicto: íntegro o alterado.

---

## 5. Glosario de términos

| Término | Significado en este sistema |
|---|---|
| **IoT (Internet of Things)** | Conjunto de dispositivos conectados que recogen datos del entorno (sensores). |
| **Hash / Huella digital** | Código corto y único que representa un dato. Si el dato cambia, el código cambia. |
| **SHA-256** | Algoritmo que se usa para calcular las huellas. Estándar reconocido internacionalmente. |
| **Tangle** | Red distribuida pública (similar a una blockchain) donde se registran las huellas. |
| **IOTA** | Organización y tecnología que desarrolla y mantiene el Tangle. |
| **MQTT** | Protocolo de mensajería ligero que utilizan los sensores IoT para enviar datos. |
| **Mosquitto** | Programa que actúa como intermediario de mensajes MQTT en el ordenador local. |
| **Block / Bloque** | Una entrada concreta en el Tangle. Tiene un identificador único (block_id). |
| **JSON** | Formato de texto estructurado, fácil de leer, usado para intercambiar datos. |
| **Python** | Lenguaje de programación en el que está escrito el sistema. |
| **Registro local** | Archivo en el ordenador que guarda los datos originales y su huella. |
| **Veredicto** | Resultado de la verificación: ÍNTEGRO (sin alterar) o ALTERADO (manipulado). |

---

## 6. Requisitos previos

> **Nota:** Este prototipo fue desarrollado y probado en **WSL 2 (Windows Subsystem for Linux)** con Ubuntu 26.04 LTS. No obstante, el sistema es compatible con cualquier entorno Linux o macOS que disponga de los requisitos indicados a continuación. Los comandos del manual están escritos para sistemas basados en Linux.

### 6.1 Python (versión 3.11)

```bash
python3 --version
```

Si no lo tiene, descárguelo desde [python.org](https://python.org).

### 6.2 Rust

Visite [rust-lang.org/tools/install](https://rust-lang.org/tools/install) y siga las instrucciones de `rustup` (el instalador oficial).

### 6.3 Mosquitto (broker MQTT)

```bash
sudo apt install mosquitto mosquitto-clients   # Ubuntu/Debian
```

### 6.4 Docker Desktop y Docker Compose

Descárguelos desde [docker.com](https://docker.com). La versión gratuita es suficiente.

---

## 7. Instalación paso a paso

**Paso 1 — Obtener el código**

```bash
git clone https://github.com/MariaBL92/iot
cd iot
```

**Paso 2 — Crear entorno virtual de Python**

```bash
python3 -m venv venv
source venv/bin/activate     # en Windows: venv\Scripts\activate
```

Cuando vea el prefijo `(venv)` en la terminal, el entorno está activo.

**Paso 3 — Instalar las dependencias**

```bash
pip install -r requirements.txt
```

**Paso 4 — Crear el archivo de configuración**

```bash
cp .env.example .env
```

Los valores por defecto ya están listos para el nodo local.

**Paso 5 — Levantar el Private Tangle (solo la primera vez)**

```bash
git clone https://github.com/iotaledger/hornet.git
cd hornet/private_tangle
./bootstrap.sh
./run.sh 4
```

Tarda entre 10 y 15 minutos. Verifique el estado en `http://localhost:8011` (usuario: `admin`, contraseña: `admin`). El indicador verde confirma que está operativo.

**En sesiones siguientes basta con:**

```bash
cd hornet/private_tangle
docker compose --profile "4-nodes" start
```

**Para apagar ordenadamente (importante):**

```bash
docker compose --profile "4-nodes" stop
```

> **Advertencia:** No cierre el equipo sin ejecutar este comando. Un apagado abrupto puede corromper la base de datos del nodo. Si ocurre, use `cleanup.sh` y repita el bootstrap.

---

## 8. Cómo usar el sistema

Active el entorno virtual en cada terminal antes de ejecutar cualquier comando: `source venv/bin/activate`

**Terminal 1 — Broker MQTT:**
```bash
mosquitto -v
```

**Terminal 2 — Simulador de sensores:**
```bash
make simulate
```
Publica una lectura de temperatura y humedad cada 2 segundos.

**Terminal 3 — Procesador y registrador:**
```bash
make subscribe
```
Recibe cada lectura, calcula su huella y la registra en el Tangle. Anote el `block_id` que aparece; lo necesitará para verificar.

**Terminal 4 — Registro local (opcional):**
```bash
tail -f data/local_registry.json
```
Muestra en tiempo real los datos originales, huellas e identificadores de bloque almacenados localmente.

---

## 9. Verificar la integridad de un registro

### 9.1 Verificación normal (resultado esperado: ÍNTEGRO)

```bash
make verify BLOCK_ID=0x1234abc...
```

El sistema recupera la huella del Tangle y la compara con la huella recalculada. Si coinciden: `ÍNTEGRO`.

### 9.2 Simulación de una alteración (resultado esperado: ALTERADO)

Edite el archivo `data/local_registry.json` y cambie un valor (por ejemplo, temperatura `24.7` por `24.8`). Vuelva a verificar:

```bash
make verify BLOCK_ID=0x1234abc...
```

Resultado: **ALTERADO**. Las huellas no coinciden — la del Tangle es la original e inviolable; la recalculada refleja el cambio local. La diferencia revela la manipulación.

## 9.3 Escenarios de validación (E1–E6)

Los siguientes escenarios permiten comprobar que el sistema detecta cualquier modificación de los datos registrados. Se requiere que la Private Tangle esté en ejecución y que se haya realizado al menos una simulación (`make subscribe` y `make simulate`).

### Preparación

1. Crear una copia de seguridad del registro local (una sola vez, antes de alterar nada):

```bash
cp data/local_registry.json data/local_registry.json.bak
```

2. Mostrar el último registro y copiar su `block_id`:

```bash
python ver.py
```

Después de cada escenario de alteración, restaurar el registro original:

```bash
cp data/local_registry.json.bak data/local_registry.json
```

### Escenarios

| ID | Escenario | Comando de alteración | Resultado esperado |
|----|-----------|-----------------------|--------------------|
| E1 | Dato íntegro | — | INTEGRO |
| E2 | Alteración de valor numérico | `python alterar.py temperatura 30.5` | ALTERADO |
| E3 | Alteración de timestamp | `python alterar.py timestamp 2026-01-01T00:00:00Z` | ALTERADO |
| E4 | Alteración de sensor_id | `python alterar.py sensor sensor_99` | ALTERADO |
| E5 | Bloque inexistente | Usar un `block_id` inválido | ERROR_CONTROLADO |
| E6 | Manipulación local (dato y hash alterados) | `python alterar.py timestamp <valor>` y `python alterar.py hash <hash_falso>` | ALTERADO (manipulación detectada) |

En cada escenario, tras la alteración, se verifica con:

```bash
python verify_cli.py --block-id <BLOCK_ID>
```

Para el escenario E5:

```bash
python verify_cli.py --block-id 0x0000000000000000000000000000000000000000000000000000000000000000
```

### Interpretación de resultados

- **stored**: hash registrado en la Tangle de IOTA (referencia inmutable).
- **computed**: hash recalculado a partir de los datos del registro local.
- **match: True**: los datos no han sido modificados (INTEGRO).
- **match: False**: los datos fueron alterados (ALTERADO).

En el escenario E6 se simula un atacante que modifica el dato y además sustituye el hash del registro local por uno coherente con el dato falso. El sistema detecta igualmente la manipulación, ya que la verificación no utiliza el hash local, sino el registrado en IOTA.

### Scripts de apoyo

- `ver.py`: muestra el último registro de `data/local_registry.json`.
- `alterar.py <campo> <valor>`: modifica un campo del último registro. Campos admitidos: `temperatura`, `humedad`, `timestamp`, `sensor` y `hash`.
---

## 10. Pruebas de validación

### 10.1 Pruebas de detección (escenarios E1-E6)

Evalúa seis escenarios: un dato íntegro (E1), cuatro tipos de alteración (E2: temperatura, E3: timestamp, E4: sensor_id, E6: humedad) y un bloque inexistente (E5).

```bash
make bench-scenarios
```

Resultado en `docs/results/scenarios.csv`. La tasa de detección esperada es del 100 %.

### 10.2 Pruebas de latencia

Miden el tiempo de registro en el Tangle (`T_reg`) y de verificación (`T_ver`) sobre N iteraciones.

```bash
make bench-latency
```

Resultado en `docs/results/latencies.csv`.

### 10.3 Análisis estadístico (opcional)

Genera un resumen estadístico y figuras de distribución a partir de los CSV anteriores.

```bash
make bench-analyze
```

Salidas en `docs/results/summary.txt` y `docs/results/figures/`. Solo es necesario si se quiere profundizar en el análisis de los resultados.
