import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    embedding_dimension: int = 1024
    embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    vision_model_id: str = "us.amazon.nova-lite-v1:0"
    hf_token: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
