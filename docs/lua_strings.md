# Работа со строками

## Конкатенация
```bash
local s = "Hello" .. " " .. "World"
```

## Pattern matching
```bash
local s = "Hello World"
local match = string.match(s, "(%w+)")
```

## Форматирование
```bash
local formatted = string.format("Value: %d", 42)
```