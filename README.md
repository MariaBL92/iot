# IoT-IOTA Integrity

Verificación de integridad de datos IoT mediante registro de hashes en una Private Tangle de IOTA

Prototipo experimental: simula sensores IoT, calcula hashes SHA-256 de sus lecturas, los registra en la red privada de IOTA y proporciona un módulo de verificación que detecta alteraciones comparando hashes.

## Arquitectura

Cuatro capas:

1. **Simulación IoT** — script que genera lecturas sintéticas (temperatura, humedad) y las publica vía MQTT.
2. **Procesamiento** — subscriber MQTT que calcula SHA-256, construye el payload y persiste localmente.
3. **Registro distribuido** — cliente IOTA que publica hashes como Tagged Data Blocks en el Tangle.
4. **Verificación** — recupera bloques del Tangle, recalcula el hash de los datos recibidos y emite veredicto íntegro/alterado.

## Requisitos

- Python 3.11+
- [Rust](https://www.rust-lang.org/tools/install) (requerido por `iota-sdk`)
- [Mosquitto](https://mosquitto.org/download/) como broker MQTT
- [Docker](https://www.docker.com/) + Docker Compose (para el private tangle local)

> En Windows, se recomienda WSL2 para evitar problemas de compilación con `iota-sdk`.

> **Nota sobre testnets públicos:** Los testnets públicos de IOTA Stardust (`api.testnet.iota.org`, `api.testnet.shimmer.network`) están offline desde mayo de 2025. El proyecto usa un private tangle local levantado con Docker.

## Instalación

```bash
git clone <url-del-repo>
cd iot

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env       # ajusta variables si necesitas
```

## Levantar el Private Tangle (Docker)

El nodo IOTA local se levanta una sola vez. Tarda ~15 minutos en estar completamente sano.

```bash
# Clonar Hornet (solo la primera vez)
git clone https://github.com/iotaledger/hornet.git
cd hornet/private_tangle

# Bootstrap: genera genesis snapshot y claves (solo la primera vez)
./bootstrap.sh

# Levantar nodos 
./run.sh 
```

Verificar que está sano: abrí `http://localhost:8011` (credenciales: `admin` / `admin`). El indicador verde confirma que el coordinador está emitiendo milestones.

Una vez sano, el nodo REST API escucha en `http://localhost:14265`.

> **Gotcha macOS:** si el contenedor `inx-coordinator` se cae durante el startup, reinicialo manualmente:
> ```bash
> docker compose start inx-coordinator
> ```

El `.env` ya está configurado para apuntar al nodo local:

```
IOTA_NODE_URL=http://localhost:14265
```

## Uso completo (Capas 1 → 4)

Cuatro terminales en paralelo:

```bash
# Terminal 1 - broker MQTT
mosquitto -v

# Terminal 2 - publica lecturas cada 2 segundos
make simulate

# Terminal 3 - consume, hashea, persiste y registra en Tangle
make subscribe

# Terminal 4 - inspecciona el registro local en vivo
bat data/local_registry.json
# o para ver solo block_ids:
jq '.[].block_id' data/local_registry.json
```

Cada entry pasa por los estados:
- `pending`: tras llegar a Capa 2, antes de intentar Tangle
- `registered`: tras éxito en el Tangle (block_id presente)
- `failed`: tras agotar reintentos (block_id sigue siendo `null`)

### Verificar la integridad de un bloque (Capa 4)

```bash
# Verifica contra los datos del registro local
make verify BLOCK_ID=0x1234abc...

# O contra un archivo externo (para probar alteraciones)
python verify_cli.py --block-id 0x1234abc... --data-file /tmp/altered.json
```

Códigos de salida del verificador:
- `0` → INTEGRO
- `1` → ALTERADO
- `2` → error (bloque no encontrado, payload corrupto, sin red, etc.)


## Benchmarks (Capa de validación, Fase 5)

```bash
# Latencia T_reg y T_ver sobre N=100 iteraciones
make bench-latency             # default N=100
N=50 make bench-latency        # con N personalizado

# Escenarios funcionales E1-E6
make bench-scenarios

# Estadísticas + figuras (lee los CSV generados)
make bench-analyze
```

Salidas en `docs/results/`:
- `latencies.csv` — latencias por iteración
- `scenarios.csv` — verdicto por escenario
- `summary.txt` — resumen estadístico legible
- `figures/latency_histogram.png` — histogramas de T_reg y T_ver
- `figures/latency_boxplot.png` — comparación de distribuciones

## Tests

```bash
make test               # unitarios (sin red, sin broker)
make test-cov           # con reporte de cobertura
make test-integration   # requieren broker + private tangle corriendo
```

## Estructura

```
iot
├── src/
│   ├── simulator/         # Capa 1
│   ├── processor/         # Capa 2
│   ├── iota/              # Capa 3
│   └── verifier/          # Capa 4
├── tests/
│   ├── unit/
│   └── integration/
├── benchmarks/            # Fase 5
├── data/
├── docs/
│   ├── results/
│   └── diagrams/
├── verify_cli.py          # CLI del verificador
├── requirements.txt
├── pyproject.toml
├── Makefile
└── .env.example
```

## Fases

| Fase | Estado | Descripción |
|------|--------|-------------|
| 0    | OK     | Setup del entorno |
| 1    | OK     | Simulador IoT (Capa 1) |
| 2    | OK     | Procesamiento y hash (Capa 2) |
| 3    | OK     | Registro en Tangle (Capa 3) — private tangle local |
| 4    | OK     | Verificación (Capa 4) |
| 5    | OK     | Benchmarks y validación |
| 6    | WIP    | Documentación final |

## Licencia

Pendiente (uso académico).
