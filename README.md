# 🤖 LocalScript AI

> **AI-агент для генерации работоспособного Lua-кода**  
> Локально • Приватно • Воспроизводимо • Без внешних LLM-вендоров

[![Hackathon](https://img.shields.io/badge/🏆%20TrueTech%20Hack-2026-red.svg)](https://git.truetecharena.ru/)
[![Author](https://img.shields.io/badge/👤%20bogomol-author-purple.svg)](https://git.truetecharena.ru/tta/true-tech-hack2026-localscript/bogomol/task-repo)
[![MWS Octapi](https://img.shields.io/badge/MWS%20Octapi-API-red.svg)](https://octapi.mws.ru/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-24.0+-blue.svg)](https://www.docker.com/)
[![Ollama](https://img.shields.io/badge/Ollama-qwen2.5--coder:1.5b-orange.svg)](https://ollama.ai/)
[![Lua 5.4](https://img.shields.io/badge/Lua-5.4-blue.svg)](https://www.lua.org/)



## 📋 О проекте

**LocalScript AI** — это агентская система, которая принимает задачу на естественном языке (русский/английский) и генерирует рабочий, валидированный **Lua 5.5** код.

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

## 🚀 Быстрый старт

### 1️⃣ Клонирование и настройка

```bash
git clone https://git.truetecharena.ru/tta/true-tech-hack2026-localscript/bogomol/task-repo.git
cd LocalScript
cp .env.example .env
```

### 2️⃣ Запуск системы

```bash
# Запустить все сервисы
docker-compose up -d --build

# Подождать ~30-60 секунд (инициализация БД + миграции)
docker-compose logs -f  # опционально: следить за логами
```
### 3️⃣ Запуск системы
```bash
# Запустите все сервисы
docker-compose up -d --build
```
>⏱️ Первый запуск:
>* Миграции применятся автоматически (~15 сек)
>* Модели Ollama загрузятся автоматически (~3-10 мин, ~3.5 GB)
>* Следите за прогрессом: docker-compose logs -f ollama

>🔁 Повторные запуски:
>* Модели уже в томе ollama_data — загрузка пропустится
>* Система стартует за ~30 секунд

### 4️⃣ Проверка работоспособности
# Проверьте статус сервисов
```bash
docker-compose ps

# Ожидаемо:
# localscript_db       Up (healthy)
# my_local_migrations  Exited (0)
# localscript_ollama   Up
# localscript_backend  Up
# my_frontend          Up
```

### 5️⃣ Открытие веб-интерфейса
```bash
🌐 Фронтенд: http://localhost:5173
🔧 Swagger API: http://localhost:8080/docs
📊 ChromaDB UI: http://localhost:8001
🤖 Ollama API: http://localhost:11434
```

### 🐛 Устранение неполадок
### ❌ "Model not found" в Ollama
```bash
# Проверить список моделей
docker-compose exec ollama ollama list

# Загрузить вручную (если авто-загрузка не сработала)
docker-compose exec ollama ollama pull qwen2.5-coder:1.5b
docker-compose exec ollama ollama pull nomic-embed-text
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

VITE_API_URL=http://localhost:8080
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
### 4. Обновляем чат
```bash
После каждого запроса генерации кода желательно создавать новый чат с помощью кнопки в верхнем правом углу
```
## 📋 Примеры использования
**Основный эндпоинты:**
* post: /api/v1/generate/lua
* post: /api/v1/generate/lua_rag

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

### 📚 Примеры документов RAG

В папке [`docs/`](docs/) вы найдёте готовые примеры документации:

1. **[lua_tables.md](docs/lua_tables.md)** — Таблицы, массивы, словари
2. **[lua_functions.md](docs/lua_functions.md)** — Функции, замыкания, рекурсия
3. **[lua_modules.md](docs/lua_modules.md)** — Модули, require, пакеты
4. **[lua_strings.md](docs/lua_strings.md)** — Строки, pattern matching
5. **[lua_error_handling.md](docs/lua_error_handling.md)** — pcall, xpcall, assert

**Как использовать:**
1. Загрузите любой файл через раздел "📚 Документы"
2. Запросите: "Как создать таблицу в Lua?"
3. RAG найдёт релевантные фрагменты и вставит в промпт
4. Получите код с учётом контекста из документации

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
│  │   (8080)    │  • Auth (JWT)                          │
│  │             │  • Generation API                      │
│  │             │  • RAG API                             │
│  │             │  • Sandbox API                         │
│  └──────┬──────┘                                        │
│         │                                               │
│    ┌────┴────┬────────────┬────────────┐                │
│    ▼         ▼            ▼            ▼                │
│ ┌─────┐ ┌─────────┐ ┌─────────┐ ┌────────────┐          │
│ │Ollama││ChromaDB │ │PostgreSQL │ │Sandbox   │          │
│ │LLM   ││Vector DB│ │Metadata │ │Lua 5.4     │          │
│ │(11434)│ (8000)  │ │(5432)   │ │Docker      │          │
│ └─────┘ └─────────┘ └─────────┘ └────────────┘          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 📊 C4 Diagram (Container Level)

<img width="1252" height="1332" alt="Containers" src="https://github.com/user-attachments/assets/023eec98-e64b-4c40-b423-607f77acb841" />


## 🔧 Разработка
### 📁 Структура проекта
```bash
LocalScript/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │  ├── auth/
│   │   │  │  ├── __init__.py
│   │   │  │  ├── endpoints.py
│   │   │  │  ├── dependencies.py
│   │   │  │  └── schemas.py
│   │   │  ├── chat/
│   │   │  │  ├── __init__.py
│   │   │  │  ├── endpoints.py
│   │   │  │  ├── dependencies.py
│   │   │  │  └── schemas.py
│   │   │  ├── document/
│   │   │  │  ├── __init__.py
│   │   │  │  ├── endpoints.py
│   │   │  │  ├── dependencies.py
│   │   │  │  └── schemas.py
│   │   │  ├── generate/
│   │   │  │  ├── __init__.py
│   │   │  │  ├── endpoints.py
│   │   │  │  ├── rag_generate.py
│   │   │  │  ├── dependencies.py
│   │   │  │  └── schemas.py
│   │   │  ├── user/
│   │   │  │  ├── __init__.py
│   │   │  │  ├── endpoints.py
│   │   │  │  ├── dependencies.py
│   │   │  │  └── schemas.py
│   │   ├── services/
│   │   │  ├── __init__.py
│   │   │  │  ├── agent/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── fix_code.py
│   │   │  │  │  └── lua_agent_graph.py
│   │   │  │  ├── user/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── base.py
│   │   │  │  │  ├── user_service.py
│   │   │  │  │  └── repository.py
│   │   │  │  ├── generation/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── base.py
│   │   │  │  │  ├── generation_service.py
│   │   │  │  │  └── repository.py
│   │   │  │  ├── message/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── base.py
│   │   │  │  │  ├── message_service.py
│   │   │  │  │  └── repository.py
│   │   │  │  ├── chat/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── base.py
│   │   │  │  │  ├── chat_service.py
│   │   │  │  │  └── repository.py
│   │   │  │  ├── document/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── base.py
│   │   │  │  │  ├── document_service.py
│   │   │  │  │  └── repository.py
│   │   │  │  ├── rag/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── chroma_client.py
│   │   │  │  │  ├── dependencies.py
│   │   │  │  │  ├── document_processor.py
│   │   │  │  │  ├── embedding_service.py
│   │   │  │  │  ├── ollama_client.py
│   │   │  │  │  ├── rag_chank.py
│   │   │  │  │  └── rag_service.py
│   │   │  │  ├── sandbox/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  └── sandbox_service.py
│   │   │  │  ├── llm/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  └── generator.py 
│   │   │  │  └── promts/
│   │   │  │  │  ├── __init__.py
│   │   │  │  │  ├── lua_agent_system_prompt.py
│   │   │  │  │  └── lua_rag_agent_prompt.py
│   │   ├── models/
│   │   │  ├── __init__.py
│   │   │  ├── user.py
│   │   │  ├── document.py
│   │   │  ├── chat.py
│   │   │  ├── message.py
│   │   │  └── generation.py           
│   │   └── core/
│   │   │  ├── __init__.py 
│   │   │  ├── database.py
│   │   │  ├── logging_settings.py
│   │   │  └── config.py 
│   ├── Dockerfile
│   ├── sandbox/
│   │   ├── Dockerfile
│   │   └── sandbox_runner.lua
│   ├── alembic/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── init.py
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   
│   │   ├── services/     
│   │   └── pages/         
│   ├── nginx.conf
│   ├── Dockerfile
│   └── package.json              
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md

```

## 🛠️ Стек технологий

### 🐍 Backend

| Технология | Версия | Назначение |
|------------|--------|------------|
| **Python** | 3.12 | Язык программирования |
| **FastAPI** | ^0.109.0 | Асинхронный REST API фреймворк |
| **Uvicorn** | ^0.27.0 | ASGI сервер для продакшена |
| **SQLAlchemy 2.0** | ^2.0.0 | ORM для работы с БД |
| **asyncpg** | ^0.29.0 | Асинхронный драйвер PostgreSQL |
| **Pydantic v2** | ^2.5.0 | Валидация данных и настройки |
| **python-jose** | ^3.3.0 | JWT-аутентификация |
| **bcrypt** | ^4.1.0 | Хэширование паролей |
| **uv** | ^0.1.0 | Современный пакетный менеджер (замена pip/poetry) |
| **alembic** | ^1.13.0 | Миграции базы данных |

### ⚛️ Frontend

| Технология | Версия | Назначение |
|------------|--------|------------|
| **React** | ^18.2.0 | UI библиотека |
| **TypeScript** | ^5.3.0 | Типизация JavaScript |
| **Vite** | ^5.0.0 | Сборщик и dev-сервер |
| **Axios** | ^1.6.0 | HTTP-клиент для API-запросов |
| **React Router** | ^6.20.0 | Навигация по приложению |
| **CSS Modules** | — | Изолированные стили компонентов |

### 🤖 AI / ML

| Технология | Версия | Назначение |
|------------|--------|------------|
| **Ollama** | latest | Локальный запуск LLM |
| **qwen2.5-coder:1.5b** | 1.5b | Легковесная модель для генерации кода |
| **ChromaDB** | ^0.4.22 | Векторная база данных для RAG |
| **nomic-embed-text** | latest | Модель эмбеддингов для поиска |

### 🗄️ Базы данных

| Технология | Версия | Назначение |
|------------|--------|------------|
| **PostgreSQL** | 15-alpine | Реляционная БД для пользователей, истории, метаданных |
| **ChromaDB** | latest | Векторное хранилище для RAG-поиска |

### 🐳 Инфраструктура

| Технология | Версия | Назначение |
|------------|--------|------------|
| **Docker** | 24.0+ | Контейнеризация сервисов |
| **Docker Compose** | 2.20+ | Оркестрация мульти-контейнерного приложения |
| **nginx** | alpine | Reverse proxy, статика, кэширование |
| **NVIDIA Container Toolkit** | любой | Доступ GPU из контейнеров |

### 🔐 Безопасность

| Инструмент | Назначение |
|------------|------------|
| **JWT (python-jose)** | Stateless аутентификация |
| **bcrypt** | Безопасное хэширование паролей |
| **Docker Sandbox** | Изолированное выполнение сгенерированного кода |
| **Security headers (nginx)** | Защита от XSS, clickjacking, MIME-sniffing |

### 📊 Мониторинг и логирование

| Инструмент | Назначение |
|------------|------------|
| **logging (Python stdlib)** | Структурированные логи backend |
| **Health checks** | Проверка доступности сервисов в docker-compose |
| **nvidia-smi** | Мониторинг потребления VRAM |

---

## 🤝 Вклад в проект

* 1. Форкни репозиторий
* 2. Создай ветку: `git checkout -b feature/my-feature`
* 3. Закоммить: `git commit -m 'feat: добавить фичу'`
* 4. Запушь: `git push origin feature/my-feature`
* 5. Открой Pull Request

**📋 Code style: `uv run ruff format . && uv run ruff check . --fix`**

## 👥 Авторы и благодарности

### 🎯 Команда - bogomol
- **Константин** — архитектура, backend, RAG, sandbox
- **Ярослав** — frontend, UI/UX, интеграция

### 🙏 Благодарности
- [Ollama](https://ollama.ai/) — локальный запуск LLM
- [ChromaDB](https://www.trychroma.com/) — векторная база
- [FastAPI](https://fastapi.tiangolo.com/) — backend фреймворк

### 🏆 Хакатон
Проект создан для **TrueTech Hackathon 2026** (MTS True Tech).  
Спасибо организаторам за поддержку!

