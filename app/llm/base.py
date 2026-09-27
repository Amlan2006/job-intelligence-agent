from typing import Literal, Protocol

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ProviderResponse(BaseModel):
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    name: str
    model: str

    async def invoke(
        self,
        messages: list[Message],
        schema: type[BaseModel] | None = None,
        task_type: str | None = None,
    ) -> ProviderResponse: ...
