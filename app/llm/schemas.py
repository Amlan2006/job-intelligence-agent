from pydantic import BaseModel, ConfigDict, Field


class FoundationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=500)
