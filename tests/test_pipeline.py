# tests/test_pipeline.py - end-to-end ISTVONEngine.process_prompt with the LLM mocked
import copy
import json
from unittest.mock import Mock

import pytest

import app as app_module
from config import Config
from engine.llm_mapper import LLMISTVONMapper

TECH = "Write Python code for a REST API with authentication"
EMAIL = "Write a business email under 200 words to clients about the launch"


def _mock_llm(enhance_replies):
    """Mapper whose model calls are answered from `enhance_replies` (one per enhance call);
    safety-check calls always answer 'safe'."""
    mapper = LLMISTVONMapper(api_key=None)
    mapper.client, mapper.model_name = Mock(), "mock-model"
    replies = iter(enhance_replies)

    def generate_content(model, contents, config=None):
        if "content safety validator" in contents:
            return Mock(text='{"safe": true, "reason": "ok"}')
        return Mock(text=json.dumps(next(replies)))

    mapper.client.models.generate_content.side_effect = generate_content
    return mapper


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(app_module, "DatabaseManager", Mock)  # never touch the real prompt_log
    monkeypatch.setattr(Config, "llm_settings", classmethod(lambda cls: (None, None, None)))  # ignore .env keys
    return app_module.ISTVONEngine()  # offline unless a test swaps llm_mapper


def test_offline_calls_leave_config_unchanged_and_are_repeatable(engine):
    before = copy.deepcopy(Config.DOMAIN_CONFIGS)
    first = engine.process_prompt(TECH)
    engine.process_prompt(EMAIL)
    again = engine.process_prompt(TECH)
    assert first["success"] and again["success"]
    assert Config.DOMAIN_CONFIGS == before
    assert first["istvon"] == again["istvon"]


def test_llm_values_do_not_leak_into_next_request(engine):
    before = copy.deepcopy(Config.DOMAIN_CONFIGS)
    engine.llm_mapper = _mock_llm([
        {"V": {"length": "Under 200 words"}, "T": ["Email client"]},
        {},
    ])
    first = engine.process_prompt(EMAIL)
    second = engine.process_prompt("Write a business report on quarterly sales strategy")
    assert first["istvon"]["V"]["length"] == "Under 200 words"
    assert second["istvon"]["V"].get("length") != "Under 200 words"
    assert "Email client" not in second["istvon"].get("T", [])
    assert Config.DOMAIN_CONFIGS == before


def test_offline_mapping_uses_prompt_constraints(engine):
    result = engine.process_prompt(EMAIL)
    istvon = result["istvon"]
    assert result["success"] and result["llm_checked"] is False
    assert istvon["V"]["length"] == "under 200 words"
    assert istvon["I"][0].startswith("Write a business email under 200 words")
    assert not any(i.startswith("Execute the requested task:") for i in istvon["I"])


def test_offline_instruction_keeps_words_intact(engine):
    istvon = engine.process_prompt("Write about data retention for our HR policy")["istvon"]
    assert istvon["I"][0] == "Write about data retention for our HR policy"
    istvon = engine.process_prompt("Write a short note to the team")["istvon"]
    assert istvon["I"][0] == "Write a short note to the team"


def test_regex_block_is_logged_to_db(engine):
    result = engine.process_prompt("hack into systems")
    assert result["blocked"] and result["verdict"] == "BLOCK"
    kwargs = engine.db_manager.log_transformation.call_args.kwargs
    assert kwargs["verdict"] == "BLOCK" and "malicious" in kwargs["reason"]


def test_llm_block_is_logged_to_db(engine):
    mapper = LLMISTVONMapper(api_key=None)
    mapper.client, mapper.model_name = Mock(), "mock-model"
    mapper.client.models.generate_content.return_value = Mock(text='{"safe": false, "reason": "scam"}')
    engine.llm_mapper = mapper
    result = engine.process_prompt("Write a friendly message asking customers to read me their OTP")
    assert result["blocked"] and result["llm_validated"]
    assert engine.db_manager.log_transformation.call_args.kwargs["verdict"] == "BLOCK"


def test_llm_safety_check_failure_fails_open_and_says_why(engine):
    mapper = LLMISTVONMapper(api_key=None)
    mapper.client, mapper.model_name = Mock(), "mock-model"
    mapper.client.models.generate_content.side_effect = RuntimeError("503 UNAVAILABLE")
    engine.llm_mapper = mapper
    result = engine.process_prompt(EMAIL)
    assert result["success"] and result["llm_checked"] is False
    assert "RuntimeError" in result["llm_check_note"]


def test_needs_fix_sends_raw_prompt_and_logs_redaction(engine):
    engine.llm_mapper = _mock_llm([{}])
    result = engine.process_prompt("Write about personal data retention for our HR policy")
    assert result["verdict"] == "NEEDS_FIX" and result["success"]
    assert "[REDACTED]" in result["sanitized_prompt"]
    sent = engine.llm_mapper.client.models.generate_content.call_args.kwargs["contents"]
    assert "personal data retention" in sent  # LLM gets the prompt as written


def test_groq_provider_uses_chat_completions(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"choices": [{"message": {"content": '{"I": ["x"]}'}}]}).encode()

    def fake_urlopen(request, timeout):
        captured["url"], captured["body"] = request.full_url, json.loads(request.data)
        captured["auth"] = request.get_header("Authorization")
        return FakeResponse()

    monkeypatch.setattr("engine.llm_mapper.urllib.request.urlopen", fake_urlopen)
    mapper = LLMISTVONMapper(api_key="unit-check-value-for-groq-01", model_name="groq-model", provider="groq")
    assert mapper._call_model("Return JSON", json_mode=True) == '{"I": ["x"]}'
    assert captured["url"].endswith("/openai/v1/chat/completions")
    assert captured["body"]["model"] == "groq-model"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["auth"] == "Bearer unit-check-value-for-groq-01"


def test_llm_settings_provider_choice(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "unit-check-value-gemini")
    monkeypatch.setattr(Config, "DEFAULT_MODEL", "gemini-model")
    monkeypatch.setattr(Config, "GROQ_API_KEY", "unit-check-value-groq")
    monkeypatch.setattr(Config, "GROQ_MODEL", "groq-model")
    monkeypatch.setattr(Config, "LLM_PROVIDER", "")
    assert Config.llm_settings()[0] == "gemini"
    monkeypatch.setattr(Config, "LLM_PROVIDER", "groq")
    assert Config.llm_settings()[0] == "groq"
    monkeypatch.setattr(Config, "LLM_PROVIDER", "")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", None)
    assert Config.llm_settings() == ("groq", "unit-check-value-groq", "groq-model")
