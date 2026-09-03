.PHONY: install model ingest serve dev test lint clean

install:            ## Install package in editable mode with dev tools
	pip install -e ".[dev]"

model:              ## Download the BGE embedding model
	python -m nutrimentor.cli.download_model

ingest:             ## Build the FAISS vector store from data/raw
	python -m nutrimentor.cli.ingest

serve:              ## Start the web server
	python -m nutrimentor.servers.flask_app

dev:                ## Start with auto-reload (development)
	python -m nutrimentor.servers.flask_app --reload

test:               ## Run unit tests
	pytest tests -m "not integration" -q

lint:               ## Lint with ruff
	ruff check src tests

clean:              ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
