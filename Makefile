run:
	python main.py

install:
	pip install -r requirements.txt

lint:
	ruff check .

format:
	ruff format .

.PHONY: run install lint format
