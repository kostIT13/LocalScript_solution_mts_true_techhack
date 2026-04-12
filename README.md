# 🤖 LocalScript AI

> **AI-агент для генерации работоспособного Lua-кода**  
> Локально • Приватно • Воспроизводимо • Без внешних LLM-вендоров

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-24.0+-blue.svg)](https://www.docker.com/)
[![Ollama](https://img.shields.io/badge/Ollama-qwen2.5--coder:1.5b-orange.svg)](https://ollama.ai/)


## 📋 О проекте

**LocalScript AI** — это агентская система, которая принимает задачу на естественном языке (русский/английский) и генерирует рабочий, валидированный **Lua 5.4** код.

### 🔑 Ключевые особенности

| Фича | Описание |
|------|----------|
| 🎯 **Локальная генерация** | Работает полностью offline через **Ollama + qwen2.5-coder:1.5b** |
| 🔒 **Приватность** | Никакие данные не покидают контур компании — нет внешних API |
| 🧠 **RAG с базой знаний** | Поиск по локальной документации в **ChromaDB** для контекстной генерации |
| 🧪 **Sandbox-валидация** | Автоматическая проверка кода в изолированном Docker-контейнере |
| 🔄 **Итеративное улучшение** | Агент задаёт уточняющие вопросы и дорабатывает код по обратной связи |
| 🐳 **Docker-деплой** | Полная воспроизводимость: `docker-compose up -d` |


## 🏆 Соответствие требованиям хакатона

* ✅ Модель: qwen2.5-coder:1.5b (легковесная, ~3.2GB при квантизации)
* ✅ Запуск: Ollama локально, полностью на GPU (без CPU offload)
* ✅ VRAM: ≤ 8.0 GB (проверено: ~5.8 GB peak при num_ctx=4096)
* ✅ Параметры: num_ctx=4096, num_predict=256, batch=1, parallel=1
* ✅ Генерация: Только локальная open-source модель (нет OpenAI/Anthropic)
* ✅ Язык: Понимает задачи на русском и английском
* ✅ Валидация: Синтаксическая проверка + выполнение в Sandbox
* ✅ Итерации: Поддержка обратной связи и уточняющих вопросов
* ✅ База знаний: Локальный ChromaDB + векторный поиск
* ✅ Воспроизводимость: Полный docker-compose + инструкции

## 🚀 Быстрый старт

### 📦 Требования

| Компонент | Версия | Зачем |
|-----------|--------|-------|
| 🐳 Docker | 24.0+ | Контейнеризация всех сервисов |
| 🐳 Docker Compose | 2.20+ | Оркестрация сервисов |
| 🎮 NVIDIA GPU | 8 GB VRAM | Запуск LLM на GPU |
| 🔧 NVIDIA Container Toolkit | любой | Доступ GPU из контейнеров |

### 1️⃣ Клонирование и настройка

```bash
# Клонировать репозиторий
git clone <repo-url>
cd LocalScript

# Создать .env файл из примера
cp .env.example .env

# Отредактировать секреты (опционально)
# Важно: SECRET_KEY должен быть уникальным
```

### 2️⃣ Запуск Ollama и загрузка модели
```bash
# Запустить Ollama (если не через docker-compose)
# Или просто дождаться авто-запуска через compose

# Загрузить модель (выполнить один раз)
docker-compose exec ollama ollama pull qwen2.5-coder:1.5b

# Проверить, что модель загружена
docker-compose exec ollama ollama list
# Ожидаемо:
# NAME                      ID              SIZE
# qwen2.5-coder:1.5b       abc123...      ~3.2 GB
```

### 3️⃣ Запуск всей системы
```bash
# Собрать и запустить все сервисы
docker-compose up -d --build

# Следить за логами
docker-compose logs -f

# Проверить статус сервисов
docker-compose ps
# Ожидаемо: все сервисы в статусе "healthy"
```

### 4️⃣ Открыть интерфейс
```bash
🌐 Фронтенд: http://localhost:5173
🔧 Swagger API: http://localhost:8000/docs
📊 ChromaDB UI: http://localhost:8001
🤖 Ollama API: http://localhost:11434
```

### Обязательно посмотрите настройки в .env.example
```bash
LOG_LEVEL=INFO

POSTGRES_DB=Mydatabase123
POSTGRES_HOST=Mydb123
POSTGRES_PASSWORD=Mypass123
POSTGRES_USER=Myuser123
DATABASE_URL=postgresql+asyncpg://Myuser123:Mypass123@Mydb123:5432/Mydatabase123

SECRET_KEY=YOUR_SECRET_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

OLLAMA_HOST=http://ollama:99999
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_LLM_MODEL=YOUR_LLM

CHROMA_HOST=chromadb
CHROMA_PORT=8000

NUM_CTX=4096
NUM_PREDICT=256
NUM_BATCH=1
NUM_PARALLEL=1
OLLAMA_LLM_MODEL=qwen2.5-coder:1.5b

VITE_API_URL=http://localhost:8000
```

## 💻 Использование

### 1. Откройте веб-интерфейс
```bash
# После запуска docker-compose up -d
# Откройте в браузере:
http://localhost:5173
```
### 2. Зарегистрируйтесь или войдите
```bash
Email: user@example.com
Пароль: secure123
```
### 3. Создайте первый запрос
```bash
Задача: "Напиши функцию sum(a, b) которая возвращает a + b"
```
## 📋 Примеры использования
### Пример 1: Простая функция
### Запрос:
```bash
Напиши функцию sum(a, b) которая возвращает a + b
```
### Ожидаемый результат
```bash
function sum(a, b)
    return a + b
end
```
### Sandbox тест:
```bash
✅ print(sum(2, 3)) → 5
✅ valid: true
✅ timing_ms: 1850
```
### Пример: RAG-запрос с базой знаний
### Предварительно: Загрузите документ lua_tables.md через раздел "📚 Документы"
### Запрос:
```bash
Как создать таблицу с начальными значениями
```
### Ожидаемый результат (с RAG-контекстом):
```bash
local person = {
    name = "Alice",
    age = 30,
    city = "Moscow"
}
```
### RAG источники:
```bash
📚 tables.txt (score: 0.82)
📚 tables.txt (score: 0.71)
```

## 🏗️ Архитектура системы
```
┌─────────────────────────────────────────────────────────┐
│                    LocalScript AI                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐                                        │
│  │  Frontend   │  React + TypeScript + Vite             │ 
│  │  (5173)     │  • Чат-интерфейс                       │
│  └──────┬──────┘  • Загрузка документов                 │
│         │ HTTPS                                         │
│         ▼                                               │
│  ┌─────────────┐                                        │
│  │   Nginx     │  Reverse proxy + static serve          │   
│  │  (5173)     │  • Проксирование /api/ → backend       │
│  └──────┬──────┘  • Gzip, кэширование                   │
│         │                                               │
│         ▼                                               │
│  ┌─────────────┐                                        │
│  │   Backend   │  FastAPI + Python 3.12                 │ 
│  │   (8000)    │  • Auth (JWT)                          │
│  │             │  • Generation API                      │
│  │             │  • RAG API                             │
│  │             │  • Sandbox API                         │
│  └──────┬──────┘                                        │
│         │                                               │
│    ┌────┴────┬────────────┬────────────┐                │
│    ▼         ▼            ▼            ▼                │
│ ┌─────┐ ┌─────────┐ ┌─────────┐ ┌────────────┐          │
│ │Ollama│ │ChromaDB │ │PostgreSQL│ │Sandbox    │         │
│ │LLM   │ │Vector DB│ │Metadata │ │Lua 5.4    │          │
│ │(11434)│ │(8000)  │ │(5432)   │ │Docker    │           │
│ └─────┘ └─────────┘ └─────────┘ └────────────┘          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 📊 C4 Diagram (Container Level)

<img width="1252" height="1332" alt="Containers" src="https://github.com/user-attachments/assets/023eec98-e64b-4c40-b423-607f77acb841" />


