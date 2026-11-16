PYTHON ?= python3
RUFF ?= ruff

.PHONY: format check
format:
	$(PYTHON) scripts/format_sources.py --ruff $(RUFF)

check:
	$(PYTHON) scripts/format_sources.py --ruff $(RUFF) --check
	$(PYTHON) scripts/check_sources.py
