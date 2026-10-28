# Variables de entorno para facilitar la lectura y el mantenimiento
PYTHON := python3
VENV := venv
VENV_BIN := $(VENV)/bin

# .PHONY indica que estas reglas no son archivos físicos, sino comandos a ejecutar
.PHONY: all install lint clean

# Regla por defecto si solo ejecutas 'make'
all: install

# Regla para crear el entorno virtual y actualizar pip
$(VENV):
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/python -m pip install --upgrade pip

# Regla 'install': Depende de que $(VENV) exista. Instala las librerías.
install: $(VENV)
	$(VENV_BIN)/pip install pydantic flake8 mypy pygame pytest

# Regla 'lint': Valida el código usando los ejecutables dentro del entorno virtual
lint:
	@echo "Ejecutando Flake8 (Estilo)..."
	$(VENV_BIN)/flake8 .
	@echo "Ejecutando MyPy (Tipado Estático)..."
	$(VENV_BIN)/mypy .

# Regla 'clean': Elimina el entorno virtual y los archivos temporales de caché
clean:
	rm -rf $(VENV)
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
