# CLAUDE.md — Contexto para Claude Code

Este archivo le da contexto a Claude Code sobre este proyecto. Léelo antes de hacer cualquier cambio.

---

## Qué es este proyecto

**Prototipo experimental de un Trabajo Fin de Máster** que verifica la integridad de datos generados por sensores IoT registrando hashes SHA-256 en un Private Tangle de IOTA.

- Todo es **simulación por software**: no hay hardware físico ni sensores reales.
- El objetivo es **demostrar viabilidad técnica** y producir métricas (latencia, tasa de detección), no construir un producto productivo.
- Stack: Python 3.11+, `paho-mqtt`, `iota-sdk`, Mosquitto, Private Tangle IOTA .

## Arquitectura — cuatro capas

| Capa | Carpeta | Responsabilidad |
|------|---------|-----------------|
| 1. Simulación IoT | `src/simulator/` | Genera lecturas sintéticas y las publica vía MQTT |
| 2. Procesamiento | `src/processor/` | Recibe MQTT, hashea SHA-256, persiste local |
| 3. Registro Tangle | `src/iota/` | Publica en IOTA Testnet como Tagged Data Block |
| 4. Verificación | `src/verifier/` + `verify_cli.py` | Recupera bloque, recalcula hash, emite veredicto |

Ver el diagrama completo en `docs/diagrams/` o el bosquejo de programación.

## Contratos críticos — NO romper

Estos invariantes son la base del sistema. Cualquier cambio que los viole rompe la verificación de integridad.

### 1. `canonical_json` es el único punto de serialización para hashing
Todo lo que se vaya a hashear o comparar pasa por `src/processor/hash_generator.py::canonical_json()`. **Prohibido** llamar a `json.dumps` directamente en cualquier flujo que produzca o consuma un hash. Si necesitas serializar para otra cosa (p. ej. logging), está bien usar `json.dumps`; pero nunca para hashing.

### 2. Frontera de privacidad: solo metadatos al Tangle
El `tangle_payload` contiene **únicamente** `{hash, sensor_id, timestamp}`. Los valores numéricos del sensor (`temperature`, `humidity`) **nunca** salen al Tangle. Los tests `test_excludes_temperature` y `test_excludes_humidity` en `tests/unit/test_payload_builder.py` protegen esta frontera; si los rompes, hay un problema de diseño.

### 3. Imports lazy de `iota-sdk`
`from iota_sdk import Client` va **dentro** de funciones (`_build_client`, etc.), nunca a nivel de módulo. Esto permite que el resto del código corra en entornos sin Rust ni `iota-sdk` instalados, y que los tests unitarios usen mocks sin instalar la SDK.

### 4. State machine del entry en `local_registry.json`
Cada entry pasa por estos estados:
- `pending` → tras hashear, antes de Tangle. `block_id: null`.
- `registered` → tras éxito en Tangle. `block_id` poblado.
- `failed` → tras agotar retries. `block_id: null`.

La transición la hace `LocalRegistry.update_block_id(hash, block_id, status)`. No la rompas.

### 5. `verify_integrity` separa errores de veredicto `ALTERADO`
- `ALTERADO` significa "verificación funcionó y detectó manipulación". Es un **éxito** del sistema.
- `VerificationError` significa "no se pudo verificar" (bloque no existe, payload corrupto). Es un **fallo**.
La distinción es crítica para reportar métricas correctamente. Mantén `VerificationError` como excepción separada del verdict dict.

## Convenciones de código

- **Python 3.11+**, `from __future__ import annotations` al inicio de todos los módulos
- **Type hints** obligatorios en signaturas públicas
- **Docstrings** en estilo Google/numpy para módulos y funciones públicas
- **Logging** vía `logger = logging.getLogger(__name__)` y `logger.info/warning/error`. Nunca `print` en código de producción
- **f-strings** para formatear mensajes humanos; logging con `%` lazy formatting (`logger.info("foo %s", x)`) para logs
- **Variables de configuración** todas en `.env`, leídas con `os.getenv("VAR", "default")`
- **Comentarios** en inglés (código y docstrings); prosa de usuario en español

## Tests

- **Unit tests** en `tests/unit/` — sin red, sin broker, sin `iota-sdk` necesario. Usan mocks.
- **Integration tests** en `tests/integration/` — marcados con `@pytest.mark.integration`. Requieren Mosquitto + IOTA Testnet activos.
- **Cobertura objetivo**: ≥90 % en módulos críticos (`hash_generator`, `payload_builder`, `local_registry`, `integrity_checker`, `tangle_writer`).

Comandos:
```bash
make test                # Solo unit tests (excluye integration por defecto)
make test-cov            # Con reporte de cobertura
make test-integration    # Solo integration (requiere infraestructura)
pytest tests/unit/test_X.py -v   # Test individual
```

**Patrón de mocks**: las funciones que llaman al exterior (`register_in_tangle`, `verify_integrity`) reciben el cliente/fetch_fn como parámetro opcional con default `None`. Los tests inyectan `MagicMock()` o funciones lambda. Si añades un módulo nuevo que llama a la red, sigue este patrón.

## Operaciones comunes

### Ejecutar el sistema end-to-end (4 terminales)
```bash
mosquitto -v                 # Terminal 1: broker
make simulate                # Terminal 2: publica lecturas cada 2s
make subscribe               # Terminal 3: procesa + hashea + Tangle
tail -f data/local_registry.json   # Terminal 4: inspecciona
```

### Verificar un bloque
```bash
make verify BLOCK_ID=0xabc123...
# Exit code: 0=INTEGRO, 1=ALTERADO, 2=error
```

### Correr benchmarks
```bash
make bench-latency       # N=100 mediciones de T_reg y T_ver
make bench-scenarios     # E1-E6 funcionales
make bench-analyze       # CSVs → summary.txt + figuras PNG
```

### Modo desarrollo sin IOTA
```bash
make subscribe-no-tangle   # subscriber sin escribir al Tangle (status='pending')
```

## Mapa del repo

```
iot-iota-integrity/
├── src/
│   ├── simulator/sensor_simulator.py    # Capa 1: generate_sensor_data, publish_loop
│   ├── processor/
│   │   ├── hash_generator.py            # CRÍTICO: canonical_json, generate_hash
│   │   ├── payload_builder.py           # CRÍTICO: build_tangle_payload (privacy boundary)
│   │   ├── local_registry.py            # LocalRegistry class, atomic writes
│   │   └── mqtt_subscriber.py           # Orquestador: process_message + run_subscriber
│   ├── iota/
│   │   ├── iota_client.py               # Lazy SDK wrapper, hex helpers (0x prefix!)
│   │   └── tangle_writer.py             # register_in_tangle (retries), fetch_block_data
│   └── verifier/integrity_checker.py    # verify_integrity, verify_from_registry
├── tests/
│   ├── unit/                            # Sin red, con mocks
│   └── integration/                     # Con broker + IOTA (marcados @pytest.mark.integration)
├── benchmarks/
│   ├── measure_latency.py               # CSV con T_reg, T_ver
│   ├── run_scenarios.py                 # CSV con verdicts E1-E6
│   └── analyze_results.py               # Stats + figuras
├── verify_cli.py                        # CLI raíz del verificador
├── pyproject.toml                       # pytest config, markers
├── requirements.txt                     # paho-mqtt, iota-sdk, python-dotenv, pytest, matplotlib
├── Makefile                             # Todas las operaciones documentadas
├── .env.example                         # Plantilla; copiar a .env
└── data/local_registry.json             # NO versionado, generado en runtime
```

## Trampas conocidas (gotchas)

### `iota-sdk` 1.1.3 exige prefijo `0x` en hex
La función `utf8_to_hex` en `src/iota/iota_client.py` debe devolver `"0x" + hex`, no solo `hex`. Si ves `Invalid hex prefix: expected '0x' but got '49'`, es esto. `hex_to_utf8` ya tolera ambos formatos.

### `paho-mqtt` v2 cambió la API de callbacks
Hay que usar `Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)` y las signaturas de callback son `(client, userdata, flags, reason_code, properties)`. Si copias snippets viejos de internet, fallarán silenciosamente.

### `sort_keys=True` no es opcional
Cualquier `json.dumps` que vaya antes de un hash debe tener `sort_keys=True`. Por eso existe `canonical_json` — para no depender de recordarlo.

### Atomic write del registry
`LocalRegistry._save` usa temp file + `os.replace`. Si añades operaciones de escritura, mantén ese patrón para evitar corrupción si el proceso se mata a mitad.

### `nohup` puede romper el flujo MQTT
Si arrancas el subscriber con `nohup ... &`, paho-mqtt puede dejar de procesar mensajes silenciosamente. Para correr en background usa `tmux` o `screen`, no `nohup`.

### `pip install --break-system-packages` en algunos sistemas
Si trabajas fuera de un venv en Ubuntu/Debian con PEP 668, necesitarás `--break-system-packages`. **Mejor**: usa siempre `venv` y evita esto.

### Encoding de payload al Tangle vs decoding
`register_in_tangle` serializa el payload completo `{hash, sensor_id, timestamp}` a JSON y luego a hex. `verify_integrity` hace el camino inverso: hex → JSON string → dict → extrae campo `"hash"`. **No** intentes decodificar directamente bytes a string asumiendo que el contenido es el hash crudo — hay un JSON intermedio.

## No hacer estas cosas

- ❌ `from iota_sdk import Client` a nivel de módulo (rompe imports sin SDK)
- ❌ `json.dumps(data)` antes de un hash (usa `canonical_json`)
- ❌ Añadir `temperature` o `humidity` a `tangle_payload` (rompe privacidad)
- ❌ `print(...)` en código de producción (usa `logger.*`)
- ❌ Hardcodear `https://api.testnet.iota.org` (usa `os.getenv("IOTA_NODE_URL")`)
- ❌ Commitear `.env` o `data/local_registry.json` (están en `.gitignore`)
- ❌ Romper `VerificationError` vs `ALTERADO` (ver Contrato 5)
- ❌ Mezclar tests unit + integration en el mismo archivo

## Estado actual

- ✅ Fases 1-5 implementadas (simulador, procesamiento, Tangle, verificador, benchmarks)
- ⏳ Fase 6: documentación final
- 91 tests unitarios pasando
- Cobertura: hash_generator 100 %, payload_builder 100 %, integrity_checker 94 %, tangle_writer 89 %, local_registry 94 %

## Antes de cerrar una sesión

1. `make test` debe pasar
2. Si tocaste código de un módulo crítico, `make test-cov` para verificar que no bajó la cobertura
3. Si modificaste `requirements.txt`, prueba `pip install -r requirements.txt` en un venv limpio
4. Si añadiste una operación nueva, documéntala en el `Makefile` y en `README.md`
5. Tag de Git al cerrar una fase: `v0.X-fase-Y-nombre`

## Referencias

- `README.md` — overview general y operaciones
- `Bosquejo_Programacion_TFM.docx` — diseño detallado del código 
- `Manual_Usuario.docx` — guía accesible para usuarios no técnicos
- IOTA docs: https://wiki.iota.org/
- paho-mqtt v2 docs: https://github.com/eclipse/paho.mqtt.python
