import logging
import json
import docker
import base64 
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SandboxResult(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0

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
            encoded_code = base64.b64encode(code.encode('utf-8')).decode('ascii')
            
            command = f'sh -c "echo \\"{encoded_code}\\" | base64 -d | lua5.4 /sandbox_runner.lua"'
            
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
            logger.error(f"Образ {self.image_name} не найден")
            return SandboxResult(
                success=False, 
                error=f"Image '{self.image_name}' not found. Run: docker-compose build --no-cache sandbox"
            )
        except Exception as e:
            logger.error(f"Sandbox error: {type(e).__name__}: {e}", exc_info=True)
            return SandboxResult(success=False, error=f"{type(e).__name__}: {str(e)}")