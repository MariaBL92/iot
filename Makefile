.PHONY: help install test test-unit test-integration test-cov \
        simulate subscribe subscribe-no-tangle verify \
        bench-latency bench-scenarios bench-analyze clean

help:
	@echo "Setup:"
	@echo "  install            Install Python dependencies"
	@echo ""
	@echo "Tests:"
	@echo "  test               Run unit tests (no network/broker)"
	@echo "  test-integration   Run integration tests (need broker + IOTA)"
	@echo "  test-cov           Unit tests with coverage report"
	@echo ""
	@echo "Run components (each in its own terminal):"
	@echo "  simulate              Run the sensor simulator (Layer 1)"
	@echo "  subscribe             Run subscriber WITH Tangle registration (L2 + L3)"
	@echo "  subscribe-no-tangle   Run subscriber WITHOUT Tangle (for local-only testing)"
	@echo "  verify BLOCK_ID=...   Verify a block (Layer 4). Usage: make verify BLOCK_ID=0xabc..."
	@echo ""
	@echo "Benchmarks (Phase 5):"
	@echo "  bench-latency      Run latency benchmark (N=100 by default)"
	@echo "  bench-scenarios    Run E1-E6 functional scenarios"
	@echo "  bench-analyze      Produce stats + figures from CSVs"
	@echo ""
	@echo "Misc:"
	@echo "  clean              Remove cache and build artifacts"

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
