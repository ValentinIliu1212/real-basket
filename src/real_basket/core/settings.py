from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_ID: str = "gpt-4o-mini"
    AGENT_NAME: str = "REALBASKET-ORCHESTRATOR"   # chat agent; the collector sub-agent is REALBASKET-COLLECTOR

    DESTATIS_GENESIS_TOKEN: str = ""
    USE_DEMO_DATA: bool = True

    DATA_DIR: str = "data_store"               # local cache (method-note index)

    # --- Method notes from reference documents (RAG retrieval, see real_basket.knowledge) ---------
    KNOWLEDGE_DIR: str = "reports/real-data"   # PDFs whose method notes / caveats are indexed
    KNOWLEDGE_RETRIEVER: str = "auto"          # bm25 | embedding | auto (embedding if OPENAI_API_KEY set)
    EMBEDDING_MODEL_ID: str = "text-embedding-3-small"
    KNOWLEDGE_TOP_K: int = 4                   # passages per search


@lru_cache
def get_settings() -> Settings:
    return Settings()
