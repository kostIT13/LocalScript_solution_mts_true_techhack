# Модули и require

## Создание модуля
-- module.lua
local M = {}
function M.hello() print("Hello") end
return M

## Использование
local module = require("module")
module.hello()