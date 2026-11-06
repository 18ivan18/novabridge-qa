# Stage 1: install dependencies, the embedding model and the app.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Dependencies come before the source, so a code change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# The model is baked into the image rather than cached in a volume. The image is about 65 MB
# larger, but the first start needs no download and the app does not depend on the model host at
# run time. Another EMBEDDING_MODEL still works: it downloads on first use unless this argument
# is changed to match.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV FASTEMBED_CACHE_PATH=/opt/models
RUN .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# Stage 2: only what runs. uv and its cache stay behind.
FROM python:3.12-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/opt/models

COPY --from=build --chown=app:app /opt/models /opt/models
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app scripts ./scripts
# Docker copies this into the empty `data` volume on first use, along with its ownership.
COPY --chown=app:app data/raw ./data/raw

USER app
EXPOSE 8000
# One worker on purpose: the job registry and the index lock live in this process's memory.
CMD ["uvicorn", "novabridge_qa.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
