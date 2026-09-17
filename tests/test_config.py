"""Local live setup must load settings without leaking or executing secrets."""

import os

import pytest

from arena import config
from arena.__main__ import main


@pytest.fixture
def local_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    for name in list(os.environ):
        if name.startswith("ARENA_") or name in {"OPENAI_API_KEY", "OPENAI_BASE_URL"}:
            monkeypatch.delenv(name)
    return tmp_path / ".env"


def test_dotenv_config_and_environment_precedence(local_env, monkeypatch):
    local_env.write_text(
        "\ufeff# local provider\nexport ARENA_LLM_MODE=live\n"
        'OPENAI_API_KEY="test#secret" # comment\n'
        "OPENAI_BASE_URL='http://localhost:1234/v1/'\n"
        "ARENA_MODEL=local-model # comment\nARENA_PRICE_INPUT_PER_M=0\n",
        encoding="utf-8",
    )
    settings = config.ArenaConfig.from_env()
    assert settings.mode == "live"
    assert settings.api_key == "test#secret"
    assert settings.base_url == "http://localhost:1234/v1"
    assert settings.model == "local-model"
    assert settings.price_input_per_m == 0
    assert "OPENAI_API_KEY" not in os.environ
    monkeypatch.setenv("ARENA_MODEL", "exported-model")
    assert config.ArenaConfig.from_env(mode="mock").model == "exported-model"
    assert config.ArenaConfig.from_env(mode="mock").mode == "mock"


def test_dotenv_values_are_literal_and_reread(local_env):
    local_env.write_text('OPENAI_API_KEY="$(do-not-execute)${SECRET}"\n')
    assert config.ArenaConfig.from_env().api_key == "$(do-not-execute)${SECRET}"
    local_env.write_text("OPENAI_API_KEY=replacement\n")
    assert config.ArenaConfig.from_env().api_key == "replacement"


def test_bad_quotes_do_not_disclose_the_secret(local_env):
    local_env.write_text('OPENAI_API_KEY="private-secret\n')
    with pytest.raises(ValueError) as exc:
        config.ArenaConfig.from_env()
    assert "OPENAI_API_KEY" in str(exc.value)
    assert "private-secret" not in str(exc.value)


@pytest.mark.parametrize("key", ["", "mock-key", "sk-replace-me"])
def test_live_run_rejects_missing_or_example_key(local_env, key, capsys):
    local_env.write_text(f"OPENAI_API_KEY={key}\n")
    assert main(["run", "--arena", "tool_use", "--framework", "vanilla", "--mode", "live"]) == 2
    assert "refusing live run" in capsys.readouterr().err


def test_missing_dotenv_keeps_mock_defaults(local_env):
    assert config.ArenaConfig.from_env().mode == "mock"
    assert config.ArenaConfig.from_env().api_key == "mock-key"


def test_codex_model_is_independent_of_api_model(local_env, monkeypatch):
    local_env.write_text("ARENA_MODEL=api-only-model\nARENA_CODEX_MODEL=subscription-model\n")
    assert config.ArenaConfig.from_env(mode="live").model == "api-only-model"
    assert config.ArenaConfig.from_env(mode="codex").model == "subscription-model"
    monkeypatch.delenv("ARENA_CODEX_MODEL", raising=False)
    local_env.write_text("ARENA_MODEL=api-only-model\n")
    assert config.ArenaConfig.from_env(mode="codex").model == "gpt-6-astra"
