# backend/Dockerfile
FROM python:3.11-slim

# 🔥 Системные зависимости: Lua + curl
RUN apt-get update && apt-get install -y \
    lua5.4 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/luac5.4 /usr/bin/luac 2>/dev/null || true

# 🔍 Проверка luac
RUN luac -v || echo "⚠️ luac не найден, валидация кода будет пропущена"

WORKDIR /app

# 🔥 Устанавливаем uv
RUN pip install --no-cache-dir uv

# 🔥 Копируем манифесты из контекста сборки (корень проекта)
# Пути относительны к context: . в docker-compose.yml
COPY pyproject.toml uv.lock ./

# 🔥 Устанавливаем зависимости
RUN uv sync --frozen --no-dev --no-editable

# 🔥 Копируем ВЕСЬ проект в контейнер
# После этого в /app будет: /app/backend/, /app/pyproject.toml, и т.д.
COPY . .

# 🔥 Создаём папки для данных
RUN mkdir -p /app/uploads /app/chroma_data

EXPOSE 8000

# 🔥 CMD будет переопределён в docker-compose, но оставим для полноты
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]