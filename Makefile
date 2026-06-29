# Sovereign Inference — common developer commands.
.DEFAULT_GOAL := help

PY_SRC := packages adapters
MYPY_SRC := packages/sip-protocol/src packages/receipt-verifier/src packages/sin-node/src packages/sin-cli/src adapters/runtime-ollama/src adapters/runtime-llamacpp/src

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Install Python (uv) and JS (pnpm) workspaces
	uv sync
	pnpm install

.PHONY: fmt
fmt: ## Auto-format Python
	uv run ruff format $(PY_SRC)

.PHONY: lint
lint: ## Lint Python (ruff)
	uv run ruff format --check $(PY_SRC)
	uv run ruff check $(PY_SRC)

.PHONY: type
type: ## Type-check core libraries (mypy --strict)
	uv run mypy $(MYPY_SRC)

.PHONY: test
test: ## Run the Python test suite
	uv run pytest

.PHONY: cov
cov: ## Run tests with coverage
	uv run pytest --cov --cov-report=term-missing

.PHONY: js-check
js-check: ## Typecheck the TypeScript SDK
	pnpm --filter @sovereign-inference/sdk typecheck

.PHONY: check
check: lint type test ## Run all Python quality gates

.PHONY: demo
demo: ## Sign and verify a sample receipt (the working slice)
	uv run sip-receipt demo > /tmp/sip-receipt.json
	uv run sip-receipt verify /tmp/sip-receipt.json

.PHONY: clean
clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache **/dist **/*.egg-info
