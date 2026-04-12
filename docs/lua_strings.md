# Работа со строками

## Конкатенация
local s = "Hello" .. " " .. "World"

## Pattern matching
local s = "Hello World"
local match = string.match(s, "(%w+)")

## Форматирование
local formatted = string.format("Value: %d", 42)