import re

def fix_lua_code(code: str) -> str:
    
    code = re.sub(r'^```lua\s*', '', code)
    code = re.sub(r'^```\s*', '', code)
    code = re.sub(r'\s*```$', '', code)
    code = code.strip()
    
    opens = code.count('function') + code.count('if') + code.count('for') + code.count('while') + code.count('repeat')
    closes = code.count('end') + code.count('until')
    
    while closes > opens and code.endswith('end'):
        code = code[:-3].strip()
        closes -= 1
    
    while opens > closes:
        code += '\nend'
        closes += 1
    
    code = code.rstrip()
    
    return code