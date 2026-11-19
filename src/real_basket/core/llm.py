"""LLM provider selection: OpenAI (api.openai.com) or Azure OpenAI.

Azure is used when OPENAI_API_TYPE=azure (or when only AZURE_OPENAI_ENDPOINT is set). On Azure the
"model" is the deployment name: AZURE_COMPLETION_MODEL for chat, AZURE_EMBEDDING_MODEL for embeddings.

`config_issues()` validates the combination of settings: errors (missing key / endpoint, unknown provider) stop
the chat agent at start-up (`require_configured`), warnings (e.g. an Azure key duplicated in OPENAI_API_KEY) are
shown in the dashboard sidebar and printed by the CLI.
"""

from __future__ import annotations

from typing import Any

from real_basket.core.settings import Settings, get_settings

API_TYPES = ("", "openai", "azure", "azure_ad", "azuread")


class LLMConfigError(RuntimeError):
    """The LLM provider settings in .env are incomplete or contradictory."""


def use_azure(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    api_type = s.OPENAI_API_TYPE.strip().lower()
    if api_type:
        return api_type in ("azure", "azure_ad", "azuread")
    return bool(s.AZURE_OPENAI_ENDPOINT)


def api_key(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    key = (s.AZURE_OPENAI_API_KEY or s.OPENAI_API_KEY) if use_azure(s) else s.OPENAI_API_KEY
    return "" if key.startswith("sk-...") else key


def config_issues(settings: Settings | None = None) -> dict[str, list[str]]:
    """{'errors': [...], 'warnings': [...]} for the provider settings (no network calls)."""
    s = settings or get_settings()
    errors: list[str] = []
    warnings: list[str] = []
    if s.OPENAI_API_TYPE.strip().lower() not in API_TYPES:
        errors.append(f"OPENAI_API_TYPE={s.OPENAI_API_TYPE!r} is unknown (use 'openai' or 'azure').")
    if use_azure(s):
        if not s.AZURE_OPENAI_ENDPOINT:
            errors.append("Azure OpenAI: AZURE_OPENAI_ENDPOINT is missing.")
        if not api_key(s):
            errors.append("Azure OpenAI: AZURE_OPENAI_API_KEY is missing.")
        if s.OPENAI_API_KEY and s.AZURE_OPENAI_API_KEY:
            warnings.append("OPENAI_API_KEY is set but ignored with Azure (AZURE_OPENAI_API_KEY is used) - leave "
                            "it empty so the key is never sent to api.openai.com.")
        elif s.OPENAI_API_KEY and not s.OPENAI_API_KEY.startswith("sk-..."):
            warnings.append("Azure OpenAI uses OPENAI_API_KEY as a fallback - move the key to "
                            "AZURE_OPENAI_API_KEY and leave OPENAI_API_KEY empty.")
        if not s.AZURE_COMPLETION_MODEL:
            warnings.append(f"AZURE_COMPLETION_MODEL is empty - '{s.OPENAI_MODEL_ID}' (OPENAI_MODEL_ID) is used as "
                            "the deployment name.")
    else:
        key = api_key(s)
        if not key:
            errors.append("OpenAI: OPENAI_API_KEY is missing (or still the placeholder 'sk-...').")
        elif not key.startswith("sk-"):
            warnings.append("OPENAI_API_KEY does not look like an OpenAI key ('sk-…'). For an Azure key set "
                            "OPENAI_API_TYPE=azure, AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.")
        if s.AZURE_OPENAI_API_KEY or s.AZURE_COMPLETION_MODEL:
            warnings.append("Azure settings are set but ignored, because OPENAI_API_TYPE is not 'azure'.")
    return {"errors": errors, "warnings": warnings}


def is_configured(settings: Settings | None = None) -> bool:
    return not config_issues(settings)["errors"]


def require_configured(settings: Settings | None = None) -> None:
    """Fail fast (chat agent start-up) instead of a 401 / connection error in the middle of a conversation."""
    errors = config_issues(settings)["errors"]
    if errors:
        raise LLMConfigError("LLM provider not configured: " + " ".join(errors) + " See .env.example.")


def completion_model_id(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.AZURE_COMPLETION_MODEL or s.OPENAI_MODEL_ID) if use_azure(s) else s.OPENAI_MODEL_ID


def embedding_model_id(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.AZURE_EMBEDDING_MODEL or s.EMBEDDING_MODEL_ID) if use_azure(s) else s.EMBEDDING_MODEL_ID


def provider_label(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return f"Azure OpenAI · {completion_model_id(s)}" if use_azure(s) else f"OpenAI · {completion_model_id(s)}"


def client_kwargs(settings: Settings | None = None) -> dict[str, Any]:
    """Constructor arguments for openai.(Async)OpenAI or openai.(Async)AzureOpenAI."""
    s = settings or get_settings()
    if use_azure(s):
        return {"api_key": api_key(s), "azure_endpoint": s.AZURE_OPENAI_ENDPOINT, "api_version": s.OPENAI_API_VERSION}
    return {"api_key": api_key(s)}


def sync_client(settings: Settings | None = None):
    """Synchronous client (used for embeddings)."""
    import openai

    s = settings or get_settings()
    cls = openai.AzureOpenAI if use_azure(s) else openai.OpenAI
    return cls(**client_kwargs(s))
