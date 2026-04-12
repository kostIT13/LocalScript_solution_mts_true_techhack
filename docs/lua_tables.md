# Таблицы в Lua

## Создание таблиц
```bash
local t = {}
local person = {name = "Alice", age = 30}
```

## Доступ к элементам
```bash
print(t.key)
print(t["key"])
```

## Итерация
```bash
for k, v in pairs(t) do end
for i, v in ipairs(array) do end
```