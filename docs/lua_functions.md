# Функции в Lua

## Объявление
function sum(a, b)
    return a + b
end

## Замыкания
function counter()
    local count = 0
    return function()
        count = count + 1
        return count
    end
end