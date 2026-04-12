# Обработка ошибок

## pcall
local success, result = pcall(function()
    error("Something went wrong")
end)

## xpcall
local function handler(err)
    print("Error:", err)
end
xpcall(function() error("test") end, handler)

## assert
local file = assert(io.open("file.txt", "r"))