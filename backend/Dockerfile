FROM python:3.12.7-slim

RUN apt-get update && apt-get install -y \
    lua5.4 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/luac5.4 /usr/bin/luac 2>/dev/null || true

RUN luac -v || echo "luac не найден, валидация кода будет пропущена"

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

ARG PYPI_INDEX_URL=https://pypi.org/simple
RUN uv sync --frozen --no-dev --no-editable --index-url ${PYPI_INDEX_URL}

COPY backend/src ./src
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/sandbox ./sandbox

RUN mkdir -p /app/uploads /app/chroma_data

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]