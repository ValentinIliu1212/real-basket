from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_ID: str = "gpt-4o-mini"
    AGENT_NAME: str = "REALBASKET-ORCHESTRATOR"

    DESTATIS_GENESIS_TOKEN: str = ""
    USE_DEMO_DATA: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
