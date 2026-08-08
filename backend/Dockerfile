# Stage 1: Build virtualenv con uv
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: Runner de producción
FROM python:3.12-slim AS runner
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Runs as an unprivileged user: a compromised process should not have root
# inside the container even though the container itself is still isolated.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]

# Stage 3: test runner, used by the `backend-test` compose profile.
# Inherits from `builder` (already ran `COPY . .`), so src/, tests/, and
# migrations/ are already present; only pytest itself is missing because the
# builder installs with --no-dev.
FROM builder AS test
WORKDIR /app
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"
CMD ["pytest", "-q"]
