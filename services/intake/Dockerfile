# Stage 1: build the virtualenv with uv
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# The layout mirrors the repository: uv.lock records chassis as ../../libs/chassis,
# and the editable install's .pth points at /srv/libs/chassis/src.
WORKDIR /srv/services/intake

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Named context (compose `additional_contexts`): the library without widening
# the build context to the whole repository.
COPY --from=chassis . /srv/libs/chassis

COPY pyproject.toml uv.lock ./
# A virtual project (no build-system): this installs the dependencies, and
# src/ is made importable through PYTHONPATH below.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .

# Stage 2: production runner
FROM python:3.12-slim AS runner
WORKDIR /srv/services/intake

COPY --from=builder /srv/services/intake/.venv .venv
COPY --from=builder /srv/libs/chassis /srv/libs/chassis
COPY --from=builder /srv/services/intake/src src
COPY --from=builder /srv/services/intake/migrations migrations
COPY --from=builder /srv/services/intake/pyproject.toml pyproject.toml

ENV PATH="/srv/services/intake/.venv/bin:$PATH" \
    PYTHONPATH=/srv/services/intake/src \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Runs as an unprivileged user: a compromised process should not have root
# inside the container even though the container itself is still isolated.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /srv/services/intake
USER appuser

CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]

# Stage 3: development server and worker. Differs from `runner` only in the
# watcher; production has nothing to watch, its source is baked into the image.
FROM runner AS dev
USER root
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/
RUN uv pip install --python .venv/bin/python watchfiles
USER appuser
# --reload-dir is explicit: the default watches the whole working directory,
# which would also cover migrations/, where a change needs a restart that
# re-runs them, not a hot reload.
CMD ["uvicorn", "infrastructure.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--app-dir", "src", "--reload", "--reload-dir", "/srv/services/intake/src", \
     "--reload-dir", "/srv/libs/chassis/src"]

# Stage 4: test runner. Inherits from `builder` (already ran `COPY . .`); only
# pytest is missing because the builder installs with --no-dev.
FROM builder AS test
RUN uv sync --frozen
ENV PATH="/srv/services/intake/.venv/bin:$PATH" \
    PYTHONPATH=/srv/services/intake/src
CMD ["pytest", "-q"]
