install:
	uv venv --allow-existing --python python3.11
	uv sync

run:
	. .venv/bin/activate && uvicorn main:app

all: install run