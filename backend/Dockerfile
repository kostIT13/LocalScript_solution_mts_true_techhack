FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    lua5.4 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/luac5.4 /usr/bin/luac 2>/dev/null || true

RUN luac -v || echo "luac не найден, валидация кода будет пропущена"

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/chroma_data

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]