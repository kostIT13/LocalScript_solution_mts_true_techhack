import re

def fix_lua_code(code: str) -> str:
    """Исправляет распространённые ошибки в сгенерированном коде."""
    
    # 1. Удаляем markdown блоки
    code = re.sub(r'^```lua\s*', '', code)
    code = re.sub(r'^```\s*', '', code)
    code = re.sub(r'\s*```$', '', code)
    code = code.strip()
    
    # 2. Считаем блоки
    opens = code.count('function') + code.count('if') + code.count('for') + code.count('while') + code.count('repeat')
    closes = code.count('end') + code.count('until')
    
    # 3. Удаляем лишние 'end' в конце
    while closes > opens and code.endswith('end'):
        code = code[:-3].strip()
        closes -= 1
    
    # 4. Добавляем недостающие 'end'
    while opens > closes:
        code += '\nend'
        closes += 1
    
    code = code.rstrip()
    
    return code