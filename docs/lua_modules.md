# Модули и require

## Создание модуля
```bash
-- module.lua
local M = {}
function M.hello() print("Hello") end
return M
```

## Использование
```bash
local module = require("module")
module.hello()
```