from dataclasses import dataclass
from dotenv import loadenv
import os

loadenv()

@dataclass(frozen=True)
class Settings:
    embedding_dimension: int = 1024
    embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    vision_model_id: str = "us.amazon.nova-lite-v1:0"
    hf_token: str = os.getenv(HF_TOKEN)
