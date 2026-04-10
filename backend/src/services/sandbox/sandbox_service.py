# backend/src/services/sandbox/sandbox_service.py
import logging
import json
import docker
import base64
import asyncio
import shlex
import time
from typing import Optional
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class SandboxResult(BaseModel):
    """Результат выполнения кода в песочнице."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    model_config = ConfigDict(extra="allow")


class SandboxService:
    """Сервис для безопасного выполнения Lua-кода в Docker-контейнере."""
    
    def __init__(self, image_name: str = "localscript-sandbox"):
        self.image_name = image_name
        self.client = None
        try:
            self.client = docker.from_env()
            logger.info(f"✅ SandboxService: подключён к Docker (образ: {image_name})")
        except docker.errors.DockerException as e:
            logger.error(f"❌ SandboxService: не удалось подключиться к Docker: {e}")
        except Exception as e:
            logger.error(f"❌ SandboxService: ошибка инициализации: {e}")

    def _execute_sync(self, code: str, timeout: int = 5) -> SandboxResult:
        """Синхронное выполнение кода (вызывается через asyncio.to_thread)."""
        if not self.client:
            return SandboxResult(success=False, error="Docker client not available")
        
        container = None
        start_time = time.time()
        
        try:
            # Кодируем код в base64 для безопасной передачи в shell
            encoded = base64.b64encode(code.encode('utf-8')).decode('ascii')
            safe_encoded = shlex.quote(encoded)
            
            # Команда: декодируем и передаём в Lua-интерпретатор через раннер
            command = ["sh", "-c", f'echo {safe_encoded} | base64 -d | lua5.4 /sandbox_runner.lua']
            
            # Запускаем контейнер с ограничениями
            container = self.client.containers.run(
                image=self.image_name,
                command=command,
                detach=True,
                remove=False,
                mem_limit="64m",
                nano_cpus=int(0.5 * 1e9),
                network_disabled=True,
                stdout=True,
                stderr=True,
            )
            
            # Ждём завершения с таймаутом
            container.wait(timeout=timeout)
            
            # Получаем логи (stdout + stderr)
            raw_output = container.logs(stdout=True, stderr=True)
            output = raw_output.decode('utf-8', errors='replace').strip()
            
            # Вычисляем время выполнения
            execution_time = round(time.time() - start_time, 3)
            
            # ─── 🔹 НАДЁЖНЫЙ ПАРСИНГ ВЫВОДА ─────────────────────────────
            # sandbox_runner.lua выводит:
            #   строка 1..N-1: вывод программы пользователя (print())
            #   строка N: JSON-отчёт раннера {"success":..., "output":..., ...}
            
            lines = output.split('\n') if output else []
            
            if not lines:
                return SandboxResult(
                    success=False,
                    error="Empty output from sandbox",
                    execution_time=execution_time
                )
            
            # Последняя строка — это JSON-метаданные от раннера
            json_line = lines[-1]
            # Всё остальное — это вывод программы пользователя
            program_output = '\n'.join(lines[:-1]).strip() if len(lines) > 1 else None
            
            try:
                data = json.loads(json_line)
                return SandboxResult(
                    success=data.get('success', False),
                    # 🔹 Приоритет: вывод программы > поле output из JSON
                    output=program_output or data.get('output'),
                    error=data.get('error'),
                    execution_time=data.get('execution_time', execution_time)
                )
            except json.JSONDecodeError as e:
                # Если последняя строка не валидный JSON — раннер упал
                logger.warning(f"⚠️ Не удалось распарсить JSON от раннера: {json_line[:100]}")
                return SandboxResult(
                    success=False,
                    error=f"Invalid sandbox output: {json_line[:200]} | {str(e)}",
                    execution_time=execution_time
                )
            # ────────────────────────────────────────────────────────────
                
        except docker.errors.ImageNotFound:
            return SandboxResult(success=False, error=f"Image '{self.image_name}' not found")
        except docker.errors.APIError as e:
            if "timeout" in str(e).lower():
                return SandboxResult(success=False, error="Превышено время выполнения (timeout)")
            return SandboxResult(success=False, error=f"Docker API error: {str(e)}")
        except asyncio.TimeoutError:
            return SandboxResult(success=False, error="Async timeout waiting for sandbox")
        except Exception as e:
            logger.error(f"Sandbox error: {type(e).__name__}: {e}", exc_info=True)
            return SandboxResult(success=False, error=f"{type(e).__name__}: {str(e)}")
        finally:
            # Гарантированная очистка контейнера
            if container:
                try:
                    container.remove(force=True)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Не удалось удалить контейнер: {cleanup_error}")

    async def execute(self, code: str, timeout: int = 5) -> SandboxResult:
        """Асинхронный входной метод для выполнения кода."""
        if not code or not code.strip():
            return SandboxResult(success=False, error="Empty code")
        
        # Выносим блокирующую операцию в отдельный поток
        return await asyncio.to_thread(self._execute_sync, code, timeout)


# 🔹 Глобальный экземпляр сервиса (синглтон)
sandbox_service = SandboxService()