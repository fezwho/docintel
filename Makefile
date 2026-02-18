.PHONY: test test-unit test-integration test-api test-cov test-watch

# Run all tests
test:
	pytest

# Run only unit tests (fast)
test-unit:
	pytest -m unit

# Run only integration tests
test-integration:
	pytest -m integration

# Run only API tests
test-api:
	pytest -m api

# Run with coverage report
test-cov:
	pytest --cov --cov-report=html --cov-report=term

# Watch mode (requires pytest-watch)
test-watch:
	ptw -- -v

# Clean test artifacts
test-clean:
	rm -rf .pytest_cache htmlcov .coverage