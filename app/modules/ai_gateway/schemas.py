import uuid

from pydantic import BaseModel


class GatewayTestRequest(BaseModel):
    resident_id: uuid.UUID
    resident_display_name: str
    prompt: str


class GatewayTestResponse(BaseModel):
    result: str
