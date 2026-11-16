PYTHON ?= python3
RUFF ?= ruff

.PHONY: format check
format:
	$(RUFF) format work scripts

check:
	$(RUFF) format --check work scripts
	$(PYTHON) scripts/check_sources.py
