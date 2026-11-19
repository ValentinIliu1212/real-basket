from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (folder with pyproject.toml): src/real_basket/core/settings.py -> parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_path(path: str | Path) -> Path:
    """Relative paths (DATA_DIR, KNOWLEDGE_DIR, ...) are resolved against the current working directory if they
    exist there, otherwise against the project root - so `streamlit run` works from any folder."""
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    return PROJECT_ROOT / p


class Settings(BaseSettings):
    # .env in the project root, overridden by a .env in the current working directory
    model_config = SettingsConfigDict(env_file=(str(PROJECT_ROOT / ".env"), ".env"), env_file_encoding="utf-8",
                                      extra="ignore")

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_ID: str = "gpt-4o-mini"
    AGENT_NAME: str = "REALBASKET-ORCHESTRATOR"   # chat agent; the collector sub-agent is REALBASKET-COLLECTOR

    # --- Azure OpenAI (used when OPENAI_API_TYPE=azure; see real_basket.core.llm) ------------------
    OPENAI_API_TYPE: str = ""                  # "" / openai -> api.openai.com | azure -> Azure OpenAI
    OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_ENDPOINT: str = ""            # e.g. https://<resource>.openai.azure.com/
    AZURE_OPENAI_API_KEY: str = ""             # falls back to OPENAI_API_KEY when empty
    AZURE_COMPLETION_MODEL: str = ""           # chat deployment name (falls back to OPENAI_MODEL_ID)
    AZURE_EMBEDDING_MODEL: str = ""            # embedding deployment name (falls back to EMBEDDING_MODEL_ID)

    DESTATIS_GENESIS_TOKEN: str = ""
    USE_DEMO_DATA: bool = True
    # Essential basket: auto = real data from the reference PDFs (KNOWLEDGE_DIR) if readable, else demo | real | demo
    DATA_SOURCE: str = "auto"

    DATA_DIR: str = "data_store"               # local cache (method-note index)

    # --- Method notes from reference documents (RAG retrieval, see real_basket.knowledge) ---------
    KNOWLEDGE_DIR: str = "reports/real-data"   # PDFs whose method notes / caveats are indexed
    KNOWLEDGE_RETRIEVER: str = "auto"          # bm25 | embedding | auto (embedding if OPENAI_API_KEY set)
    EMBEDDING_MODEL_ID: str = "text-embedding-3-small"
    KNOWLEDGE_TOP_K: int = 4                   # passages per search


@lru_cache
def get_settings() -> Settings:
    return Settings()
