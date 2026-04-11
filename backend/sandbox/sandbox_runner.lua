local cjson_ok, cjson = pcall(require, "cjson")
if not cjson_ok then
    io.write('{"success":false,"error":"Module cjson not found: ' .. tostring(cjson) .. '","execution_time":0}\n')
    io.flush()
    os.exit(1)
end

local safe_env = {
    print = function(...)
        local args = {...}
        for i, v in ipairs(args) do
            io.write(tostring(v))
            if i < #args then io.write("\t") end
        end
        io.write("\n")
    end,
    error = error, 
    type = type,
    tostring = tostring,
    tonumber = tonumber,
    pairs = pairs,
    ipairs = ipairs,
    select = select,
    unpack = table.unpack or unpack,
    
    math = math,
    string = string,
    table = table,
    
    os = { clock = os.clock, date = os.date, time = os.time, difftime = os.difftime },
    io = { write = io.write, flush = io.flush },
    
    package = nil,
    debug = nil,
    coroutine = nil,
    dofile = nil,
    loadfile = nil,
    require = nil,
    load = nil,
    getfenv = nil,
    setfenv = nil,
}

local code = io.read("*a")
if not code or code == "" then
    io.write(cjson.encode({
        success = false,
        error = "Empty code",
        execution_time = 0
    }) .. "\n")
    io.flush()
    os.exit(0)
end

local start_time = os.clock()
local TIMEOUT = tonumber(os.getenv("LUA_SANDBOX_TIMEOUT")) or 5

debug.sethook(function()
    if os.clock() - start_time > TIMEOUT then
        error("Timeout exceeded (" .. TIMEOUT .. "s)", 2)
    end
end, "", 1000)

local result, err = pcall(function()
    local func, compile_err = load(code, "sandbox", "t", safe_env)
    if not func then 
        error("Compile error: " .. tostring(compile_err)) 
    end
    
    local ok, run_err = pcall(func)
    if not ok then 
        error("Runtime error: " .. tostring(run_err)) 
    end
end)

local execution_time = math.min(os.clock() - start_time, TIMEOUT)
local output = {
    success = result,
    output = result and "OK" or nil,
    error = err and tostring(err) or nil,
    execution_time = execution_time,
}

io.write(cjson.encode(output) .. "\n")
io.flush()