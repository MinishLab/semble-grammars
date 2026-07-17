help:
	@echo "install    - uv sync + pre-commit install"
	@echo "test       - run pytest with coverage"
	@echo "lint       - run ruff check and pydoclint"
	@echo "typecheck  - run mypy"
	@echo "fix        - run pre-commit on all files"

install:
	uv sync --all-extras
	uv run pre-commit install

fix:
	uv run pre-commit run --all-files

test:
	uv run pytest --cov=semble_grammars --cov-report=term-missing

lint:
	uv run ruff check .
	uv run pydoclint semble_grammars/ tools/ setup.py

typecheck:
	uv run mypy semble_grammars/ tools/ setup.py
