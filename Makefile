.PHONY: help install test test-unit test-integration test-cov \
        simulate subscribe subscribe-no-tangle verify \
        bench-latency bench-scenarios bench-analyze clean

help:
	@echo "Setup:"
	@echo "  install            Instalar las dependencias de Python"
	@echo ""
	@echo "Tests:"
	@echo "  test               Ejecutar tests unitarios (sin red/broker)"
	@echo "  test-integration   Ejecutar tests de integración (requiere broker + IOTA)"
	@echo "  test-cov           Tests unitarios con reporte de cobertura"
	@echo ""
	@echo "Ejecutar componentes (cada uno en su propia terminal):"
	@echo "  simulate              Ejecutar el simulador de sensores (Capa 1)"
	@echo "  subscribe             Ejecutar el subscriber CON registro en el Tangle (L2 + L3)"
	@echo "  subscribe-no-tangle   Ejecutar el subscriber SIN Tangle (solo para pruebas locales)"
	@echo "  verify BLOCK_ID=...   Verificar un bloque (Capa 4). Uso: make verify BLOCK_ID=0xabc..."
	@echo ""
	@echo "Benchmarks (Fase 5):"
	@echo "  bench-latency      Ejecutar benchmark de latencia (N=100 por defecto)"
	@echo "  bench-scenarios    Ejecutar escenarios funcionales E1-E6"
	@echo "  bench-analyze      Generar estadísticas + figuras a partir de los CSVs"
	@echo ""
	@echo "Varios:"
	@echo "  clean              Eliminar caché y artefactos de compilación"

install:
	pip install -r requirements.txt

test test-unit:
	pytest tests/unit

test-integration:
	pytest tests/integration -m integration

test-cov:
	pytest tests/unit --cov=src --cov-report=term-missing

simulate:
	python -m src.simulator.sensor_simulator --sensor-id sensor_01 --interval 2

subscribe:
	python -m src.processor.mqtt_subscriber

subscribe-no-tangle:
	python -m src.processor.mqtt_subscriber --no-tangle

verify:
	@if [ -z "$(BLOCK_ID)" ]; then echo "Usage: make verify BLOCK_ID=<id>"; exit 1; fi
	python verify_cli.py --block-id $(BLOCK_ID)

bench-latency:
	python -m benchmarks.measure_latency --n $${N:-100}

bench-scenarios:
	python -m benchmarks.run_scenarios

bench-analyze:
	python -m benchmarks.analyze_results

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov coverage.xml
