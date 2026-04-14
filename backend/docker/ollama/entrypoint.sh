#!/bin/sh
set -e

echo "🚀 Starting Ollama server..."

# Запускаем сервер в фоне
ollama serve &
SERVER_PID=$!

# Ждём готовности API (используем wget или встроенный curl)
echo "⏳ Waiting for Ollama API..."
for i in $(seq 1 60); do
    # Пробуем разные способы проверки
    if command -v curl >/dev/null 2>&1; then
        if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
            echo "✅ Ollama API ready!"
            break
        fi
    elif command -v wget >/dev/null 2>&1; then
        if wget -q --spider http://localhost:11434/api/tags 2>/dev/null; then
            echo "✅ Ollama API ready!"
            break
        fi
    else
        # Fallback: просто ждём фиксированное время
        sleep 2
        echo "⚠️ No curl/wget, assuming API ready after delay"
        break
    fi
    sleep 1
done

# Авто-загрузка моделей
echo "📦 Checking models..."
for model in "qwen2.5-coder:1.5b" "nomic-embed-text"; do
    # Проверяем через API, а не через ollama list
    if curl -sf http://localhost:11434/api/tags 2>/dev/null | grep -q "$model" 2>/dev/null; then
        echo "✅ $model already exists"
    else
        echo "⬇️ Pulling $model..."
        ollama pull "$model" || {
            echo "❌ Failed to pull $model, continuing anyway..."
        }
        echo "✅ $model download attempt completed"
    fi
done

echo "🔄 Keeping Ollama running..."
wait $SERVER_PID