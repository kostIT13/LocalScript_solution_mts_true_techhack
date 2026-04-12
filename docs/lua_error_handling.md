# Обработка ошибок

## pcall
```bash
local success, result = pcall(function()
    error("Something went wrong")
end)
```

## xpcall
```bash
local function handler(err)
    print("Error:", err)
end
xpcall(function() error("test") end, handler)
```

## assert
```bash
local file = assert(io.open("file.txt", "r"))
```