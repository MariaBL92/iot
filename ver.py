"""
Muestra el último registro almacenado en el registro local (data/local_registry.json).

Uso:
    python ver.py
"""
import json

with open("data/local_registry.json") as f:
    data = json.load(f)

print(json.dumps(data[-1], indent=2))
