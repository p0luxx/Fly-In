# Environment variables for easier maintenance and readability
PYTHON := python3
VENV := venv
VENV_BIN := $(VENV)/bin

# Default map for 'run' and 'debug' rules
# You can override this by running: make run MAP=maps/hard/01_maze_nightmare.txt
MAP ?= maps/easy/01_linear_path.txt

# .PHONY indicates these rules are not physical files, but commands to execute
.PHONY: all install run debug lint clean

# Default rule when just running 'make'
all: install

# Rule to create the virtual environment and upgrade pip
$(VENV):
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/python -m pip install --upgrade pip

# 'install' rule: Depends on $(VENV) existing. Installs required libraries.
install: $(VENV)
	$(VENV_BIN)/pip install pydantic flake8 mypy pygame pytest

# 'run' rule: Executes the main application script.
run: $(VENV)
	$(VENV_BIN)/python fly_in.py $(MAP)

# 'debug' rule: Starts the script in debug mode using pdb.
debug: $(VENV)
	$(VENV_BIN)/python -m pdb fly_in.py $(MAP)

# 'lint' rule: Runs the strictly required static analysis commands
lint: $(VENV)
	@echo "Running Flake8 (Style)..."
	$(VENV_BIN)/flake8 .
	@echo "Running MyPy (Static Typing)..."
	$(VENV_BIN)/mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

# 'clean' rule: Removes the virtual environment and temporary cache files
clean:
	rm -rf $(VENV)
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
