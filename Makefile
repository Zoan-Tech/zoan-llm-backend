install:
	uv venv --allow-existing --python python3.11
	uv sync

run:
	. .venv/bin/activate && uvicorn main:app

proto:
	python -m grpc_tools.protoc -I./handler/grpc/protos --python_out=./handler/grpc/grpc_generated/completion --pyi_out=./handler/grpc/grpc_generated/completion --grpc_python_out=./handler/grpc/grpc_generated/completion ./handler/grpc/protos/completion.proto

all: install run