# Stage 1: Build virtualenv con uv
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Named context (compose `additional_contexts`): the lock resolves chassis as
# ../libs/chassis, i.e. /libs/chassis from /app, without widening the build
# context to the whole repository.
COPY --from=chassis . /libs/chassis
# A named context ignores .dockerignore: drop the host's virtualenv and caches
# so they do not reach the runner image.
RUN rm -rf /libs/chassis/.venv /libs/chassis/.pytest_cache

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
# The editable install's .pth points here, so the library must exist at runtime.
COPY --from=builder /libs/chassis /libs/chassis
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

# Stage 3: development server, used by the `backend` compose service.
# Inherits from `runner` rather than `builder` so development keeps the
# unprivileged user and the slim image, and differs from production in exactly
# one thing: the watcher. Production has nothing to watch — its source is baked
# into the image, not mounted — so carrying watchfiles there would be dead weight.
FROM runner AS dev
USER root
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/
RUN uv pip install --python /app/.venv/bin/python watchfiles
USER appuser
# --reload-dir is explicit: the default watches the whole working directory,
# which would also cover /app/migrations, where a change needs the process to
# restart and re-run the migration, not to hot-reload the app.
CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--app-dir", "src", "--reload", "--reload-dir", "/app/src", "--reload-dir", "/libs/chassis/src"]

# Stage 4: test runner, used by the `backend-test` compose profile.
# Inherits from `builder` (already ran `COPY . .`), so src/, tests/, and
# migrations/ are already present; only pytest itself is missing because the
# builder installs with --no-dev.
FROM builder AS test
WORKDIR /app
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"
CMD ["pytest", "-q"]
