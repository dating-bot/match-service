set dotenv-load := true
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

manage := "uv run"

default:
    @just --choose

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
