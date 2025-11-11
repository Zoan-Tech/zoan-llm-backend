install:
	uv venv --allow-existing
	uv pip install -e .

run:
	. .venv/bin/activate && uvicorn main:app

all: install run