set -e

echo "🚀 Starting Ollama server..."

/bin/ollama serve &
SERVER_PID=$!

echo "⏳ Waiting for Ollama API..."
for i in $(seq 1 60); do
    if /bin/curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ Ollama API ready!"
        break
    fi
    sleep 1
done

echo "📦 Checking models..."
for model in "qwen2.5-coder:1.5b" "nomic-embed-text"; do
    if /bin/ollama list 2>/dev/null | grep -q "$model"; then
        echo "✅ $model already exists"
    else
        echo "⬇️ Pulling $model..."
        /bin/ollama pull "$model"
        echo "✅ $model downloaded!"
    fi
done

echo "🔄 Keeping Ollama running..."
wait $SERVER_PID