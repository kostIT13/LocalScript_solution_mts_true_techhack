FROM python:3.11-slim

WORKDIR /app

# Устанавливаем Lua для валидации
RUN apt-get update && apt-get install -y lua5.4 && rm -rf /var/lib/apt/lists/*

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]