import logging, json, docker, base64, asyncio, shlex
from typing import Optional
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class SandboxResult(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    model_config = ConfigDict(extra="allow")


class SandboxService:
    def __init__(self, image_name: str = "localscript-sandbox"):
        self.image_name = image_name
        try:
            self.client = docker.from_env()
            logger.info("SandboxService подключён к Docker")
        except Exception as e:
            logger.error(f"Не удалось подключиться к Docker: {e}")
            self.client = None

    def _execute_sync(self, code: str, timeout: int = 5) -> SandboxResult:
        if not self.client:
            return SandboxResult(success=False, error="Docker client not available")
        
        container = None
        try:
            encoded = base64.b64encode(code.encode('utf-8')).decode('ascii')
            safe_encoded = shlex.quote(encoded)
            command = ["sh", "-c", f'echo {safe_encoded} | base64 -d | lua5.4 /sandbox_runner.lua']
            
            container = self.client.containers.run(
                image=self.image_name, command=command, detach=True, remove=False,
                mem_limit="64m", nano_cpus=int(0.5 * 1e9), network_disabled=True,
                stdout=True, stderr=True,
            )
            
            exit_status = container.wait(timeout=timeout)
            result = container.logs(stdout=True, stderr=True)
            output = result.decode('utf-8').strip()
            
            try:
                data = json.loads(output)
                return SandboxResult(**data)
            except json.JSONDecodeError:
                return SandboxResult(success=False, error=output)
                
        except docker.errors.ImageNotFound:
            return SandboxResult(success=False, error=f"Image '{self.image_name}' not found")
        except docker.errors.APIError as e:
            if "timeout" in str(e).lower():
                return SandboxResult(success=False, error="Превышено время выполнения")
            return SandboxResult(success=False, error=f"Docker error: {str(e)}")
        except Exception as e:
            logger.error(f"Sandbox error: {type(e).__name__}: {e}")
            return SandboxResult(success=False, error=f"{type(e).__name__}: {str(e)}")
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

    async def execute(self, code: str, timeout: int = 5) -> SandboxResult:
        return await asyncio.to_thread(self._execute_sync, code, timeout)


sandbox_service = SandboxService()