import logging
import json
import docker
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SandboxResult(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float


class SandboxService:
    def __init__(self, image_name: str = "localscript-sandbox"):
        self.image_name = image_name
        try:
            self.client = docker.from_env()
            logger.info("SandboxService подключён к Docker")
        except Exception as e:
            logger.error(f"Не удалось подключиться к Docker: {e}")
            self.client = None

    def execute(self, code: str, timeout: int = 5) -> SandboxResult:
        if not self.client:
            return SandboxResult(success=False, error="Docker client not available")
        
        try:
            escaped_code = code.replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
            command = f'sh -c "echo \\"{escaped_code}\\" | lua5.4 /sandbox_runner.lua"'
            
            result = self.client.containers.run(
                image=self.image_name,
                command=command,
                remove=True,
                mem_limit="64m",
                nano_cpus=int(0.5 * 1e9),
                network_disabled=True,
                stdout=True,
                stderr=True,
            )
            
            output = result.decode('utf-8').strip()
            try:
                data = json.loads(output)
                return SandboxResult(**data)
            except json.JSONDecodeError:
                return SandboxResult(success=False, error=output)
                
        except docker.errors.ImageNotFound:
            return SandboxResult(success=False, error=f"Image '{self.image_name}' not found")
        except Exception as e:
            logger.error(f"Sandbox error: {e}", exc_info=True)
            return SandboxResult(success=False, error=str(e))