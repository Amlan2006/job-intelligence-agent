import httpx
from pydantic import BaseModel

from app.llm.base import Message, ProviderResponse


class GroqProvider:
    name = "groq"

    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str, timeout: float):
        self.client, self.api_key, self.model, self.timeout = client, api_key, model, timeout

    async def invoke(
        self,
        messages: list[Message],
        schema: type[BaseModel] | None = None,
        task_type: str | None = None,
    ) -> ProviderResponse:
        if not self.api_key or not self.model:
            raise RuntimeError("Groq fallback is not configured")
        serialized = [m.model_dump() for m in messages]
        payload = {"model": self.model, "messages": serialized}
        if schema is not None:
            serialized.insert(
                0,
                {
                    "role": "system",
                    "content": "Return only JSON matching this schema: "
                    + str(schema.model_json_schema()),
                },
            )
            payload["response_format"] = {"type": "json_object"}
        response = await self.client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") or {}
        return ProviderResponse(
            content=data["choices"][0]["message"]["content"],
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
