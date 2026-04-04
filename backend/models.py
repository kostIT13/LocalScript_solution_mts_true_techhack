from pydantic import BaseModel

class GenerateRequest(BaseModel):
    task: str