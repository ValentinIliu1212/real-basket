"""Provider selection: OpenAI vs Azure OpenAI (no network calls)."""

import openai
import pytest

from real_basket.agents.orchestrator import AzureOpenAIModel, create_model
from real_basket.core import llm
from real_basket.core.settings import get_settings

AZURE = {"OPENAI_API_TYPE": "azure", "OPENAI_API_VERSION": "2024-02-15-preview",
         "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/", "AZURE_OPENAI_API_KEY": "azure-key",
         "AZURE_COMPLETION_MODEL": "gpt-4o", "AZURE_EMBEDDING_MODEL": "text-embedding-3-large"}
OPENAI = {"OPENAI_API_TYPE": "", "AZURE_OPENAI_ENDPOINT": "", "AZURE_OPENAI_API_KEY": "",
          "AZURE_COMPLETION_MODEL": "", "AZURE_EMBEDDING_MODEL": "",
          "OPENAI_API_KEY": "sk-test", "OPENAI_MODEL_ID": "gpt-4o-mini",
          "EMBEDDING_MODEL_ID": "text-embedding-3-small"}


@pytest.fixture
def env(monkeypatch):
    def apply(values):
        for k, v in values.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()
        return get_settings()
    yield apply
    get_settings.cache_clear()


def test_azure_settings_are_used(env):
    s = env({**OPENAI, **AZURE})
    assert llm.use_azure(s) and llm.is_configured(s)
    assert llm.completion_model_id(s) == "gpt-4o"
    assert llm.embedding_model_id(s) == "text-embedding-3-large"
    assert llm.client_kwargs(s) == {"api_key": "azure-key", "azure_endpoint": "https://example.openai.azure.com/",
                                    "api_version": "2024-02-15-preview"}
    assert isinstance(llm.sync_client(s), openai.AzureOpenAI)
    model = create_model()
    assert isinstance(model, AzureOpenAIModel)
    assert model.config["model_id"] == "gpt-4o"


def test_azure_key_falls_back_to_openai_key(env):
    s = env({**OPENAI, **AZURE, "AZURE_OPENAI_API_KEY": "", "OPENAI_API_KEY": "shared-key"})
    assert llm.api_key(s) == "shared-key"


def test_plain_openai_is_default(env):
    s = env(OPENAI)
    assert not llm.use_azure(s) and llm.is_configured(s)
    assert llm.completion_model_id(s) == "gpt-4o-mini"
    assert llm.client_kwargs(s) == {"api_key": "sk-test"}
    model = create_model()
    assert not isinstance(model, AzureOpenAIModel)


def test_placeholder_key_is_not_configured(env):
    s = env({**OPENAI, "OPENAI_API_KEY": "sk-..."})
    assert not llm.is_configured(s)
    with pytest.raises(llm.LLMConfigError):
        llm.require_configured(s)


def test_clean_configs_have_no_issues(env):
    assert llm.config_issues(env(OPENAI)) == {"errors": [], "warnings": []}
    assert llm.config_issues(env({**OPENAI, **AZURE, "OPENAI_API_KEY": ""})) == {"errors": [], "warnings": []}


def test_azure_key_duplicated_in_openai_key_is_warned(env):
    s = env({**OPENAI, **AZURE, "OPENAI_API_KEY": "azure-key"})
    issues = llm.config_issues(s)
    assert not issues["errors"] and any("OPENAI_API_KEY" in w for w in issues["warnings"])
    assert llm.client_kwargs(s)["api_key"] == "azure-key"            # Azure key goes to Azure only


def test_azure_key_used_with_openai_provider_is_warned(env):
    s = env({**OPENAI, "OPENAI_API_KEY": "0123456789abcdef0123456789abcdef"})     # looks like an Azure key
    issues = llm.config_issues(s)
    assert not issues["errors"] and any("does not look like an OpenAI key" in w for w in issues["warnings"])


def test_incomplete_azure_config_fails_fast(env):
    s = env({**OPENAI, **AZURE, "AZURE_OPENAI_ENDPOINT": "", "OPENAI_API_TYPE": "azure", "OPENAI_API_KEY": ""})
    assert any("AZURE_OPENAI_ENDPOINT" in e for e in llm.config_issues(s)["errors"])
    with pytest.raises(llm.LLMConfigError):
        llm.require_configured(s)
    assert llm.config_issues(env({**OPENAI, "OPENAI_API_TYPE": "azzure"}))["errors"]


def test_orchestrator_refuses_to_start_without_provider(env):
    from real_basket.agents.orchestrator import create_orchestrator

    env({**OPENAI, "OPENAI_API_KEY": ""})
    with pytest.raises(llm.LLMConfigError):
        create_orchestrator()
