"""
Modifica un campo del último registro de data/local_registry.json para
simular una alteración de los datos (escenarios de validación E2–E6).

Uso:
    python alterar.py <campo> <valor>

Campos admitidos:
    temperatura, humedad, timestamp, sensor, hash

Ejemplos:
    python alterar.py temperatura 30.5
    python alterar.py timestamp 2026-01-01T00:00:00Z
    python alterar.py sensor sensor_99

Antes de alterar, crear una copia de seguridad:
    cp data/local_registry.json data/local_registry.json.bak
Para restaurar el registro original:
    cp data/local_registry.json.bak data/local_registry.json
"""
import json
import sys

path = "data/local_registry.json"

if len(sys.argv) != 3:
    print("Uso: python alterar.py <campo> <valor>")
    sys.exit(1)

campo, valor = sys.argv[1], sys.argv[2]

with open(path) as f:
    data = json.load(f)

e = data[-1]
r = e["raw_data"]
campos = {
    "temperatura": "temperature",
    "humedad": "humidity",
    "timestamp": "timestamp",
    "sensor": "sensor_id",
}

if campo in campos:
    clave = campos[campo]
    antes = r[clave]
    r[clave] = float(valor) if campo in ("temperatura", "humedad") else valor
elif campo == "hash":
    antes = e["hash"]
    e["hash"] = valor
else:
    print("Campo no válido. Use: temperatura, humedad, timestamp, sensor o hash")
    sys.exit(1)

print(f"Alterado {campo}: {antes} -> {valor}")

with open(path, "w") as f:
    json.dump(data, f, indent=2)
