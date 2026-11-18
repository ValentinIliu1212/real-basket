from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_ID: str = "gpt-4o-mini"
    # Name of the interactive chat agent (front door). The monitoring flow agents are named
    # f"{AGENT_NAME_PREFIX}-PLANNER", "-COLLECTOR", "-VALIDATOR", "-ANALYST", "-REPORTER".
    AGENT_NAME: str = "REALBASKET-ORCHESTRATOR"
    AGENT_NAME_PREFIX: str = "REALBASKET"
    FLOW_TEMPERATURE: float = 0.3

    DESTATIS_GENESIS_TOKEN: str = ""
    USE_DEMO_DATA: bool = True

    # --- Non-deterministic monitoring flow: data store + guardrails ---------------------------
    DATA_DIR: str = "data_store"
    MAX_SOURCE_ATTEMPTS: int = 3          # fetch attempts per dataset before escalating to a human
    MAX_INVESTIGATION_STEPS: int = 4      # drill-down tool calls per run
    MAX_REPLANS: int = 1                  # analyst -> planner loops per run
    MAX_NODE_EXECUTIONS: int = 30         # hard cap on graph node executions per run
    RUN_TIMEOUT_S: int = 900              # wall-clock budget per run
    DEVIATION_THRESHOLD_PP: float = 1.0   # |essential - CPI| above this requires an investigation
    CONFIDENCE_THRESHOLD: float = 0.7     # below this a human must approve before publishing
    # Re-using stored, validated data (planned re-use or fallback when fresh data is lost): at most this
    # many trailing months may be carried forward with the last observed value (flagged in the report).
    MAX_CARRY_FORWARD_MONTHS: int = 3
    # Probability that a demo "primary" source returns faulty data (outliers, gaps, missing
    # provenance) so the validation loop has something to do. Set 0 for clean demo data.
    DEMO_FAULT_RATE: float = 0.35
    DEMO_FAULT_SEED: int | None = None    # set for reproducible fault injection (tests / demos)


@lru_cache
def get_settings() -> Settings:
    return Settings()
