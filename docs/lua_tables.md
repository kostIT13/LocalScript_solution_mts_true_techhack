# Таблицы в Lua

## Создание таблиц
local t = {}
local person = {name = "Alice", age = 30}

## Доступ к элементам
print(t.key)
print(t["key"])

## Итерация
for k, v in pairs(t) do end
for i, v in ipairs(array) do end