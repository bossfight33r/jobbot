run:
	uv run python main.py

setup:
	uv run python setup_session.py

sync:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

.PHONY: run setup sync lint format
