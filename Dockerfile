# syntax=docker/dockerfile:1
#
# Workspace validation image for Milestone 1 (workspace foundation). The root pyproject.toml is a
# virtual uv workspace coordinator with no application code, so there is no application runtime
# entrypoint yet. This image only proves the uv workspace builds and both packages import cleanly;
# it is NOT an application runtime image. A future milestone replaces the CMD below with a real
# service entrypoint under services/.

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-dev

FROM python:3.13-slim

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

# Workspace integrity check only - not an application runtime command.
CMD ["python", "-c", "import credit_core, credit_desk_contracts; print('workspace import check ok:', credit_core.__name__, credit_desk_contracts.__name__)"]
