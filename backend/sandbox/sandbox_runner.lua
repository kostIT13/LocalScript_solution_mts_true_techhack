local cjson_ok, cjson = pcall(require, "cjson")
if not cjson_ok then
    io.write(cjson.encode({
        success = false,
        error = "Module cjson not found",
        execution_time = 0
    }) .. "\n")
    io.flush()
    os.exit(1)
end

local safe_env = {}

safe_env.print = function(...)
    local args = {...}
    for i, v in ipairs(args) do
        io.write(tostring(v))
        if i < #args then io.write("\t") end
    end
    io.write("\n")
end
safe_env.type = type
safe_env.tostring = tostring
safe_env.tonumber = tonumber
safe_env.pairs = pairs
safe_env.ipairs = ipairs
safe_env.select = select
safe_env.unpack = table.unpack or unpack
safe_env.math = math
safe_env.string = string
safe_env.table = table

safe_env.os = { clock = os.clock, date = os.date, time = os.time, difftime = os.difftime }
safe_env.io = { write = io.write, flush = io.flush }

safe_env.package = nil
safe_env.debug = nil
safe_env.coroutine = nil
safe_env.dofile = nil
safe_env.loadfile = nil
safe_env.require = nil

local code = io.read("*a")
if not code or code == "" then
    io.write(cjson.encode({
        success = false,
        error = "Empty code",
        execution_time = 0
    }) .. "\n")
    io.flush()
    return
end

local start_time = os.clock()
local TIMEOUT = tonumber(os.getenv("LUA_SANDBOX_TIMEOUT")) or 5

debug.sethook(function(event)
    if os.clock() - start_time > TIMEOUT then
        error("Timeout exceeded (" .. TIMEOUT .. "s)", 2)
    end
end, "", 1000) 

local result, err = pcall(function()
    local func, compile_err = load(code, "sandbox", "t", safe_env)
    if not func then error("Compile error: " .. compile_err) end
    
    local ok, run_err = pcall(func)
    if not ok then error("Runtime error: " .. run_err) end
end)

local output = {
    success = result,
    result = result and "OK" or nil,
    error = err and tostring(err) or nil,
    execution_time = math.min(os.clock() - start_time, TIMEOUT), 
}

io.write(cjson.encode(output) .. "\n")
io.flush()