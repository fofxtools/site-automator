.PHONY: fmt lint check black ruff

fmt:
	black src/ tests/ examples/

lint:
	ruff check src/ tests/ examples/

check: fmt lint
black: fmt
ruff: lint
