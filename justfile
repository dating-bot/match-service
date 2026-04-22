set dotenv-load := true
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

manage := "uv run"

default:
    @just --choose

generate-match-api:
    buf lint
    buf format --write
    just generate-match-api-{{ os() }}

alias generate-match-api-macos := generate-match-api-linux

generate-match-api-linux:
    rm -rf match_api
    mkdir -p match_api
    docker run --rm -v ./match_api:/match_api:rw -v ./api:/api:ro -w / ghcr.io/astral-sh/uv:python3.13-bookworm-slim \
        uv run --with protoletariat==3.3.10,grpclib[protobuf]==0.4.9,mypy-protobuf==3.7.0,grpcio_tools==1.71.2 \
            protol --in-place --create-package --python-out match_api \
            protoc --protoc-path="python3 -m grpc_tools.protoc" --proto-path=api --python_out=. --grpclib_python_out=. --mypy_out=. \
                match_api/v1/match.proto

generate-match-api-windows:
    Remove-Item -Recurse -Force .\match_api
    mkdir match_api
    docker run --rm -v .\match_api:/match_api:rw -v .\api:/api:ro -w / ghcr.io/astral-sh/uv:python3.13-bookworm-slim \
        uv run --with protoletariat==3.3.10,grpclib[protobuf]==0.4.9,mypy-protobuf==3.7.0,grpcio_tools==1.71.2 \
            protol --in-place --create-package --python-out match_api \
            protoc --protoc-path="python3 -m grpc_tools.protoc" --proto-path=api --python_out=. --grpclib_python_out=. --mypy_out=. \
                match_api/v1/match.proto

lint:
    {{ manage }} ruff format .
    {{ manage }} ruff check --fix .
    {{ manage }} mypy . --install-types --non-interactive --ignore-missing-imports --disable-error-code var-annotated --disable-error-code import-untyped --disable-error-code type-abstract
    {{ manage }} basedpyright .

run-tests:
    {{ manage }} pytest --failed-first --exitfirst --verbose --no-header --numprocesses auto

migrate:
    {{ manage }} alembic upgrade head

deploy:
    rsync -r --info=progress2 -ahv . \
        --filter=':- .gitignore' \
        --exclude=".git" \
        ${SSH_TARGET}:${SSH_TARGET_PATH}

remote-execute *cmd:
    ssh ${SSH_TARGET} "cd ${SSH_TARGET_PATH} && {{ cmd }}"

remote-logs service="match_service" tail="50":
    ssh ${SSH_TARGET} "cd ${SSH_TARGET_PATH} && docker compose logs --no-log-prefix --tail {{ tail }} {{ service }}" | jlf
